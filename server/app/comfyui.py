from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import secrets
import threading
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from websockets.asyncio.client import connect as websocket_connect

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field, ValidationError, model_validator
from starlette.responses import RedirectResponse, StreamingResponse

from .auth import UserResponse, current_user
from .configs.constants import settings
from .danbooru import DanbooruError, search_danbooru_tags, validate_danbooru_tags
from .database import (
    create_image_generation as create_image_generation_record,
    create_media_asset,
    generation_elapsed_seconds,
    get_image_generation,
    get_reusable_media,
    update_image_generation_status,
)
from .generation_events import generation_event_broker, generation_key
from .moss import MossSettings, layout_prompt as moss_layout_prompt
from .prompts import (
    IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_TAG_USER_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT,
)
from .storage import (
    StorageError,
    download_file as storage_download_file,
    enabled as storage_enabled,
    read_url as storage_read_url,
    upload_file as storage_upload_file,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/generation/image", tags=["image generation"])
_COMFYUI_TIMEOUT_SECONDS = 30
_VLLM_TIMEOUT_SECONDS = 600
_SSE_HEARTBEAT_SECONDS = 15
_MAX_SEED = 2**63 - 1
_MAX_IMAGE_INPUT_SIZE = 50 * 1024 * 1024
_FILE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_DEFAULT_SAMPLER = "er_sde"
_DEFAULT_SCHEDULER = "simple"
_QWEN21_PROMPT_ENHANCER = "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors"
_QWEN21_PE_NODES = ("TextGenerate", "BatchImagesNode", "ResizeAndPadImage", "StringCompare", "ComfySwitchNode")
_QWEN21_TURBO_SCHEDULER = "qwen_2_1_turbo"
_QWEN21_TURBO_SIGMAS = "1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0"
_EDIT_MODELS = {
    "qwen_image_2_1": {
        "checkpoint": "Qwen/qwen_image_2.1_turbo_bf16.safetensors",
        "text_encoder": "qwen3vl_8b_int8_convrot.safetensors",
        "vae": "qwen_image_2.1_vae_bf16.safetensors",
        "clip_type": "qwen_image",
        "steps": 8,
        "scheduler": _QWEN21_TURBO_SCHEDULER,
        "nodes": ("TextEncodeQwenImage21", "QwenImage21Cache", "ManualSigmas", "SamplerCustomAdvanced", "KSamplerSelect", "RandomNoise", "CFGGuider", "ImageScaleToTotalPixels"),
    },
    "flux3_klein": {
        "checkpoint": "flux3-image-klein-int8-convrot.safetensors",
        "text_encoder": "qwen3vl_4b_int8_convrot.safetensors",
        "vae": "flux3-klein-vae.safetensors",
        "clip_type": "flux3",
        "steps": 16,
        "nodes": ("ReferenceMultiLatent", "TextGenerate", "BatchImagesNode", "ResizeAndPadImage", "ImageScaleToTotalPixels"),
    },
}
_FLUX3_PROMPT_UPSAMPLER = "qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors"
_PROGRESS_UNSET = object()
_progress_lock = threading.Lock()
_progress_states: dict[str, dict[str, Any]] = {}


class LoraSelection(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    strength: float = Field(default=1.0)


ModelFamily = Literal["anima", "illustrious", "flux3_klein", "moss", "qwen_image_2_1"]
_MOSS_CHECKPOINT = "MOSS/moss_image_sft_bf16.safetensors"
_MOSS_ENCODER = "qwen3.5_9b_int8_convrot.safetensors"
_MOSS_VAE = "flux2-vae_small.safetensors"
_MOSS_DMD_LORA = "MOSS/lora_latest.safetensors"


class ImageSource(BaseModel):
    file_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    file_index: int | None = Field(default=None, ge=0, le=9)

    @model_validator(mode="after")
    def exactly_one_source(self) -> "ImageSource":
        if (self.file_id is None) == (self.file_index is None):
            raise ValueError("source에는 file_id 또는 file_index 하나만 필요합니다.")
        return self


class ImageGenerationRequest(BaseModel):
    model_family: ModelFamily = "anima"
    moss: MossSettings | None = None
    positive_prompt_prefix: str = Field(default="", max_length=5000)
    prompt: str = Field(min_length=1, max_length=5000)
    prompt_enhancement_enabled: bool = False
    improved_prompt: str | None = Field(default=None, max_length=5000)
    negative_prompt_prefix: str = Field(default="", max_length=5000)
    negative_prompt: str = Field(default="", max_length=5000)
    checkpoint: str = Field(min_length=1, max_length=255)
    loras: list[LoraSelection] = Field(default_factory=list)
    cfg: float = Field(default=4, ge=0, le=20)
    steps: int = Field(default=30, ge=1, le=100)
    sampler_name: str = Field(default=_DEFAULT_SAMPLER, min_length=1, max_length=64)
    scheduler: str = Field(default=_DEFAULT_SCHEDULER, min_length=1, max_length=64)
    width: int = Field(default=1024, ge=16, le=16384, multiple_of=8)
    height: int = Field(default=1024, ge=16, le=16384, multiple_of=8)
    seed: int | None = Field(default=None, ge=0, le=_MAX_SEED)

    @model_validator(mode="before")
    @classmethod
    def edit_defaults(cls, values: Any) -> Any:
        if isinstance(values, dict) and values.get("model_family") == "moss":
            values = dict(values)
            values.setdefault("cfg", 3.0)
            values.setdefault("steps", 50)
            values.setdefault("sampler_name", "euler")
            values.setdefault("scheduler", "sgm_uniform")
            return values
        if not isinstance(values, dict) or values.get("model_family") not in _EDIT_MODELS:
            return values
        values = dict(values)
        if values["model_family"] == "qwen_image_2_1":
            values.setdefault("prompt_enhancement_enabled", True)
        values.setdefault("cfg", 1.0)
        values.setdefault("steps", _EDIT_MODELS[values["model_family"]]["steps"])
        values.setdefault("sampler_name", "euler")
        values.setdefault("scheduler", _EDIT_MODELS[values["model_family"]].get("scheduler", "simple"))
        values.setdefault("denoise", 1.0)
        return values


class ImageToImageGenerationRequest(ImageGenerationRequest):
    source: ImageSource
    references: list[ImageSource] = Field(default_factory=list, max_length=9)
    denoise: float = Field(default=0.65, ge=0, le=1)

    @model_validator(mode="after")
    def require_supported_i2i_family(self) -> "ImageToImageGenerationRequest":
        if self.model_family == "moss":
            raise ValueError("MOSS는 T2I에서만 사용할 수 있습니다.")
        return self


class ImageGenerationOptions(BaseModel):
    prompt_enhancer_available: bool = False
    model_family: ModelFamily
    checkpoints: list[str]
    loras: list[str]
    embeddings: list[str]
    samplers: list[str]
    schedulers: list[str]
    default_checkpoint: str
    default_sampler: str
    default_scheduler: str
    default_cfg: float
    default_steps: int


class ImageOutput(BaseModel):
    url: str
    filename: str
    subfolder: str
    type: str


class ImageGenerationStatus(BaseModel):
    prompt_id: str
    status: str
    progress: float = Field(default=0, ge=0, le=100)
    queue_position: int | None = Field(default=None, ge=1)
    created_at: datetime | None = None
    elapsed_seconds: float = Field(default=0, ge=0)
    images: list[ImageOutput] = Field(default_factory=list)


class ImageGenerationAccepted(BaseModel):
    prompt_id: str
    status: Literal["queued"]
    client_id: str
    generation_id: str
    progress: float = Field(default=0, ge=0, le=100)
    created_at: datetime
    elapsed_seconds: float = Field(default=0, ge=0)


def _progress_key(prompt_id: str, user_id: uuid.UUID) -> str:
    return f"{user_id}:{prompt_id}"


def generation_progress(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any]:
    with _progress_lock:
        state = _progress_states.get(_progress_key(prompt_id, user_id), {})
        return {
            "status": state.get("status"),
            "progress": float(state.get("progress", 0)),
            "queue_position": state.get("queue_position"),
        }


def reset_generation_progress(prompt_id: str, user_id: uuid.UUID) -> bool:
    return _set_progress_state(prompt_id, user_id, status="queued", progress=0, queue_position=None, node=None)


def generation_node(prompt_id: str, user_id: uuid.UUID) -> str | None:
    with _progress_lock:
        node = _progress_states.get(_progress_key(prompt_id, user_id), {}).get("node")
    return node if isinstance(node, str) else None


def _set_progress_state(
    prompt_id: str,
    user_id: uuid.UUID,
    *,
    status: Any = _PROGRESS_UNSET,
    progress: Any = _PROGRESS_UNSET,
    queue_position: Any = _PROGRESS_UNSET,
    node: Any = _PROGRESS_UNSET,
) -> bool:
    key = _progress_key(prompt_id, user_id)
    with _progress_lock:
        state = _progress_states.setdefault(
            key, {"status": None, "progress": 0.0, "queue_position": None, "node": None}
        )
        previous = state.copy()
        if status is not _PROGRESS_UNSET:
            state["status"] = status
        if progress is not _PROGRESS_UNSET:
            state["progress"] = max(0.0, min(100.0, float(progress)))
        if queue_position is not _PROGRESS_UNSET:
            state["queue_position"] = queue_position
        if node is not _PROGRESS_UNSET:
            state["node"] = node
        return state != previous


def record_comfy_progress(
    prompt_id: str,
    user_id: uuid.UUID,
    event_name: str,
    data: dict[str, Any],
    *,
    accepted_prompt_id: str | None = None,
) -> bool:
    event_prompt_id = data.get("prompt_id")
    if event_prompt_id is not None and event_prompt_id not in {prompt_id, accepted_prompt_id}:
        return False
    if event_name == "execution_start":
        return _set_progress_state(
            prompt_id, user_id, status="processing", progress=0, queue_position=None, node=None
        )
    if event_name == "executing":
        if data.get("node") is None:
            return False
        return _set_progress_state(
            prompt_id,
            user_id,
            status="processing",
            queue_position=None,
            node=str(data["node"]),
        )
    if event_name == "progress":
        value = data.get("value")
        maximum = data.get("max")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not isinstance(maximum, (int, float)) or maximum <= 0:
            return False
        return _set_progress_state(
            prompt_id,
            user_id,
            status="processing",
            progress=value / maximum * 100,
            queue_position=None,
        )
    if event_name == "progress_state":
        nodes = data.get("nodes")
        if not isinstance(nodes, dict):
            return False
        values = [
            node.get("value", 0) / node.get("max", 1) * 100
            for node in nodes.values()
            if isinstance(node, dict)
            and isinstance(node.get("value"), (int, float))
            and isinstance(node.get("max"), (int, float))
            and node.get("max", 0) > 0
        ]
        if not values:
            return False
        return _set_progress_state(
            prompt_id,
            user_id,
            status="processing",
            progress=max(values),
            queue_position=None,
        )
    if event_name == "execution_error":
        return _set_progress_state(prompt_id, user_id, status="failed")
    return False


def _comfy_websocket_url(client_id: str) -> str:
    parsed = urlsplit(settings.comfyui_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, "/ws", urlencode({"clientId": client_id}), ""))


async def stream_comfy_progress(client_id: str, stop_event: asyncio.Event) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    async with websocket_connect(_comfy_websocket_url(client_id), open_timeout=5, ping_interval=20) as socket:
        while not stop_event.is_set():
            try:
                raw_message = await asyncio.wait_for(socket.recv(), timeout=1)
            except asyncio.TimeoutError:
                continue
            if isinstance(raw_message, bytes):
                continue
            try:
                message = json.loads(raw_message)
            except (TypeError, json.JSONDecodeError):
                continue
            event_name = message.get("type") if isinstance(message, dict) else None
            data = message.get("data") if isinstance(message, dict) else None
            if isinstance(event_name, str) and isinstance(data, dict):
                yield event_name, data


def _queue_position(prompt_id: str) -> int | None:
    try:
        queue = _request_json("GET", "/queue")
    except _ComfyUIError:
        return None
    for queue_name in ("queue_running", "queue_pending"):
        entries = queue.get(queue_name)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if isinstance(entry, (list, tuple)) and len(entry) > 1 and entry[1] == prompt_id:
                return index + 1
    return None


class PromptEnhancementRequest(BaseModel):
    model_family: ModelFamily = "anima"
    prompt: str = Field(min_length=1, max_length=5000)


class PromptEnhancementContent(BaseModel):
    contents: str = Field(min_length=1, max_length=5000)


class PromptEnhancementResponse(BaseModel):
    improved_prompt: PromptEnhancementContent


@router.get("/options", response_model=ImageGenerationOptions)
def image_options(
    family: ModelFamily = Query(default="anima"),
    _: UserResponse = Depends(current_user),
) -> ImageGenerationOptions:
    try:
        return _image_options(family)
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/enhance-prompt", response_model=PromptEnhancementResponse)
def enhance_prompt(
    payload: PromptEnhancementRequest,
    _: UserResponse = Depends(current_user),
) -> PromptEnhancementResponse:
    try:
        return _enhance_prompt(payload.prompt, payload.model_family)
    except (DanbooruError, _VLLMError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("", response_model=ImageGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_image_generation(
    payload: ImageGenerationRequest,
    user: UserResponse = Depends(current_user),
) -> ImageGenerationAccepted:
    return _submit_image_generation(payload, user)


@router.post("/i2i", response_model=ImageGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_image_to_image_generation(
    payload: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    user: UserResponse = Depends(current_user),
) -> ImageGenerationAccepted:
    try:
        request = ImageToImageGenerationRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc
    try:
        _validate_model_choice(request, _image_options(request.model_family))
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    _validate_image_sources(request, files)
    resolved = [await _resolve_image_source(source, files, user) for source in [request.source, *request.references]]
    source_file_id, source_filename, _, _ = resolved[0]
    try:
        input_names = [_upload_comfy_input(content, filename, media_type) for _, filename, content, media_type in resolved]
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _submit_image_generation(
        request,
        user,
        input_image=input_names[0],
        input_references=input_names[1:],
        reference_images=[{"file_id": item[0], "filename": item[1]} for item in resolved[1:]],
        source_file_id=source_file_id,
        source_filename=source_filename,
        generation_mode="i2i",
        denoise=request.denoise,
    )


def _submit_image_generation(
    payload: ImageGenerationRequest,
    user: UserResponse,
    *,
    input_image: str | None = None,
    source_file_id: str | None = None,
    source_filename: str | None = None,
    input_references: list[str] | None = None,
    reference_images: list[dict[str, str]] | None = None,
    generation_mode: Literal["t2i", "i2i"] = "t2i",
    denoise: float = 1.0,
) -> ImageGenerationAccepted:
    try:
        options = _image_options(payload.model_family)
        _validate_model_choice(payload, options)
        prompt, seed = _build_prompt(payload, input_image=input_image, denoise=denoise, input_references=input_references)
        client_id = str(uuid.uuid4())
        response = _request_json(
            "POST",
            "/prompt",
            {"prompt": prompt, "client_id": client_id},
        )
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise HTTPException(status_code=502, detail="ComfyUI가 생성 작업 ID를 반환하지 않았습니다.")
    generation_id, created_at = create_image_generation_record(
        user_id=user.id,
        prompt_id=prompt_id,
        client_id=client_id,
        prompt=payload.prompt,
        improved_prompt=payload.improved_prompt.strip() if payload.prompt_enhancement_enabled and payload.improved_prompt else None,
        negative_prompt=payload.negative_prompt,
        positive_prompt_prefix=payload.positive_prompt_prefix,
        negative_prompt_prefix=payload.negative_prompt_prefix,
        checkpoint=payload.checkpoint,
        loras=[lora.model_dump() for lora in payload.loras],
        cfg=payload.cfg,
        steps=payload.steps,
        sampler_name=payload.sampler_name,
        scheduler=payload.scheduler,
        width=payload.width,
        height=payload.height,
        seed=seed,
        model_family=payload.model_family,
        generation_mode=generation_mode,
        source_file_id=source_file_id,
        source_filename=source_filename,
        reference_images=reference_images or [],
        denoise=denoise,
        moss=payload.moss.model_dump() if payload.model_family == "moss" and payload.moss else {},
        prompt_enhancement_enabled=payload.prompt_enhancement_enabled,
    )
    return ImageGenerationAccepted(
        prompt_id=prompt_id,
        status="queued",
        client_id=client_id,
        generation_id=str(generation_id),
        progress=0,
        created_at=created_at,
        elapsed_seconds=0,
    )


def _validate_image_sources(request: ImageToImageGenerationRequest, files: list[UploadFile]) -> None:
    if request.references and request.model_family not in _EDIT_MODELS:
        raise HTTPException(status_code=422, detail="추가 참조 이미지는 참조 생성 모드에서만 사용할 수 있습니다.")
    indices = [source.file_index for source in [request.source, *request.references] if source.file_index is not None]
    if sorted(indices) != list(range(len(files))):
        raise HTTPException(status_code=422, detail="입력 이미지와 업로드 파일의 순서가 일치하지 않습니다.")


async def _resolve_image_source(
    source: ImageSource,
    files: list[UploadFile],
    user: UserResponse,
) -> tuple[str, str, bytes, str]:
    if not storage_enabled():
        raise HTTPException(status_code=503, detail="Storage가 설정되지 않아 I2I 입력 이미지를 저장할 수 없습니다.")
    if source.file_id:
        record = get_reusable_media(source.file_id, user.id)
        if record is None or record["media_kind"] != "image":
            raise HTTPException(status_code=404, detail="선택한 이미지를 찾을 수 없습니다.")
        try:
            content, stored_type = storage_download_file(file_id=source.file_id, owner_id=str(user.id))
        except StorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        media_type = record["content_type"] or stored_type
        if not media_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="이미지 파일만 사용할 수 있습니다.")
        create_media_asset(
            user_id=user.id,
            storage_file_id=source.file_id,
            filename=record["filename"],
            content_type=media_type,
            media_kind="image",
            size=len(content),
        )
        return source.file_id, record["filename"], content, media_type
    if source.file_index is None or source.file_index >= len(files):
        raise HTTPException(status_code=422, detail="입력 이미지 파일을 찾을 수 없습니다.")
    upload = files[source.file_index]
    media_type = upload.content_type or ""
    if not media_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="이미지 파일만 사용할 수 있습니다.")
    content = await upload.read(_MAX_IMAGE_INPUT_SIZE + 1)
    if not content:
        raise HTTPException(status_code=422, detail="빈 이미지 파일은 사용할 수 없습니다.")
    if len(content) > _MAX_IMAGE_INPUT_SIZE:
        raise HTTPException(status_code=413, detail="I2I 입력 이미지는 50MB 이하여야 합니다.")
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", (upload.filename or "image.png").split("/")[-1])[:255]
    try:
        file_id = storage_upload_file(content=content, media_type=media_type, owner_id=str(user.id))
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    create_media_asset(
        user_id=user.id,
        storage_file_id=file_id,
        filename=filename,
        content_type=media_type,
        media_kind="image",
        size=len(content),
    )
    return file_id, filename, content, media_type


def _upload_comfy_input(content: bytes, filename: str, media_type: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    if extension not in {"png", "jpg", "jpeg", "webp"}:
        extension = "png"
    comfy_filename = f"local_field_i2i_{uuid.uuid4().hex}.{extension}"
    boundary = f"----LocalField{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{comfy_filename}"\r\n'
        f"Content-Type: {media_type}\r\n\r\n"
    ).encode() + content + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        "true\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    request = UrlRequest(
        _comfy_url("/upload/image"),
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_COMFYUI_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read())
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 입력 이미지 업로드가 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("ComfyUI 입력 이미지 업로드에 연결할 수 없습니다.") from exc
    name = result.get("name") if isinstance(result, dict) else None
    subfolder = result.get("subfolder", "") if isinstance(result, dict) else ""
    if not isinstance(name, str) or not name or not isinstance(subfolder, str):
        raise _ComfyUIError("ComfyUI 입력 이미지 업로드 응답이 올바르지 않습니다.")
    return f"{subfolder}/{name}" if subfolder else name


@router.get("/{prompt_id}/events")
async def image_generation_events(
    prompt_id: str,
    client_id: str = Query(min_length=1, max_length=128),
    user: UserResponse = Depends(current_user),
) -> StreamingResponse:
    generation = _require_owned_generation(prompt_id, user.id)
    if generation["client_id"] != client_id:
        raise HTTPException(status_code=404, detail="생성 결과를 찾을 수 없습니다.")
    return StreamingResponse(
        _stream_generation_events(prompt_id, client_id, user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{prompt_id}", response_model=ImageGenerationStatus)
def image_generation_status(
    prompt_id: str,
    user: UserResponse = Depends(current_user),
) -> ImageGenerationStatus:
    _require_owned_generation(prompt_id, user.id)
    try:
        return _history_generation_status(prompt_id, user.id)
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/{prompt_id}/cancel", response_model=ImageGenerationStatus)
def cancel_image_generation(
    prompt_id: str,
    user: UserResponse = Depends(current_user),
) -> ImageGenerationStatus:
    generation = _require_owned_generation(prompt_id, user.id)
    if generation["status"] == "cancelled":
        return _cancelled_image_status(generation, user.id)
    if generation["status"] not in {"queued", "processing"}:
        return _history_generation_status(prompt_id, user.id)
    try:
        dispatched = cancel_comfy_generation(prompt_id)
        if not dispatched:
            current = _history_generation_status(prompt_id, user.id)
            if current.status in {"completed", "failed", "cancelled"}:
                return current
            raise HTTPException(status_code=409, detail="이미 처리 중인 작업이라 취소할 수 없습니다.")
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    update_image_generation_status(prompt_id=prompt_id, user_id=user.id, status="cancelled")
    cancelled = get_image_generation(prompt_id, user.id) or generation
    data = {
        "prompt_id": prompt_id,
        "status": "cancelled",
        "progress": generation_progress(prompt_id, user.id)["progress"],
        "queue_position": None,
        **_image_timing(prompt_id, user.id, cancelled),
    }
    generation_event_broker.publish(
        key=generation_key("image", user.id, prompt_id),
        event="cancelled",
        data=data,
    )
    return ImageGenerationStatus(**data)


async def _stream_generation_events(prompt_id: str, client_id: str, user_id: uuid.UUID):
    key = generation_key("image", user_id, prompt_id)
    async with generation_event_broker.subscribe(key) as events:
        generation = await asyncio.to_thread(get_image_generation, prompt_id, user_id)
        if generation is None or generation["client_id"] != client_id:
            yield _sse_message("failed", {"prompt_id": prompt_id, "status": "failed", "message": "생성 결과를 찾을 수 없습니다."})
            return

        current_status = str(generation["status"])
        if current_status == "completed":
            try:
                images = await asyncio.to_thread(_stored_image_outputs, generation, user_id)
            except StorageError as exc:
                yield _sse_message("error", {"prompt_id": prompt_id, "message": str(exc)})
                return
            yield _sse_message(
                "completed",
                ImageGenerationStatus(
                    prompt_id=prompt_id,
                    status="completed",
                    images=images,
                    created_at=generation["created_at"],
                    elapsed_seconds=generation_elapsed_seconds(generation),
                ).model_dump(mode="json"),
            )
            return
        if current_status == "failed":
            yield _sse_message(
                "failed",
                {
                    "prompt_id": prompt_id,
                    "status": "failed",
                    "progress": 0,
                    "queue_position": None,
                    **_image_timing(prompt_id, user_id, generation),
                },
            )
            return
        if current_status == "cancelled":
            yield _sse_message("cancelled", _cancelled_image_status(generation, user_id).model_dump(mode="json"))
            return
        progress_state = generation_progress(prompt_id, user_id)
        yield _sse_message(
            "status",
            {
                "prompt_id": prompt_id,
                "status": current_status,
                "progress": progress_state["progress"],
                "queue_position": progress_state["queue_position"] or _queue_position(prompt_id),
                **_image_timing(prompt_id, user_id, generation),
            },
        )

        while True:
            try:
                message = await asyncio.wait_for(events.get(), timeout=_SSE_HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield _sse_message(message["event"], message["data"])
            if message["event"] in {"completed", "failed", "cancelled", "error"}:
                return


def _image_timing(prompt_id: str, user_id: uuid.UUID, generation: dict[str, Any] | None = None) -> dict[str, Any]:
    generation = generation or get_image_generation(prompt_id, user_id)
    if generation is None:
        return {"created_at": None, "elapsed_seconds": 0}
    created_at = generation.get("created_at")
    return {
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "elapsed_seconds": generation_elapsed_seconds(generation),
    }


def _cancelled_image_status(generation: dict[str, Any], user_id: uuid.UUID) -> ImageGenerationStatus:
    return ImageGenerationStatus(
        prompt_id=generation["prompt_id"],
        status="cancelled",
        progress=generation_progress(generation["prompt_id"], user_id)["progress"],
        queue_position=None,
        **_image_timing(generation["prompt_id"], user_id, generation),
    )


def _history_generation_status(prompt_id: str, user_id: uuid.UUID) -> ImageGenerationStatus:
    generation = get_image_generation(prompt_id, user_id)
    if generation is not None and generation.get("status") == "cancelled":
        return _cancelled_image_status(generation, user_id)
    history = _request_json("GET", f"/history/{prompt_id}")
    entry = history.get(prompt_id)
    progress_state = generation_progress(prompt_id, user_id)
    if not isinstance(entry, dict):
        current_status = progress_state["status"] or "queued"
        if current_status == "processing":
            update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="processing")
        elif current_status == "failed":
            update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
        timing = _image_timing(prompt_id, user_id)
        return ImageGenerationStatus(
            prompt_id=prompt_id,
            status=current_status,
            progress=progress_state["progress"],
            queue_position=progress_state["queue_position"] or _queue_position(prompt_id),
            **timing,
        )

    raw_status = entry.get("status")
    comfy_status: dict[str, Any] = raw_status if isinstance(raw_status, dict) else {}
    status_name = str(comfy_status.get("status_str", ""))
    if status_name in {"error", "failed"}:
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
        return ImageGenerationStatus(
            prompt_id=prompt_id,
            status="failed",
            progress=progress_state["progress"],
            **_image_timing(prompt_id, user_id),
        )
    if comfy_status.get("completed") is True:
        raw_images = _raw_image_outputs(entry.get("outputs"))
        _sync_generation_output(prompt_id, user_id, raw_images)
        return ImageGenerationStatus(
            prompt_id=prompt_id,
            status="completed",
            progress=100,
            images=_image_outputs(prompt_id, user_id, entry.get("outputs")),
            **_image_timing(prompt_id, user_id),
        )
    update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="processing")
    return ImageGenerationStatus(
        prompt_id=prompt_id,
        status="processing",
        progress=progress_state["progress"],
        **_image_timing(prompt_id, user_id),
    )


def _sse_message(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _require_owned_generation(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any]:
    generation = get_image_generation(prompt_id, user_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="생성 결과를 찾을 수 없습니다.")
    return generation


def _sync_generation_output(prompt_id: str, user_id: uuid.UUID, images: list[dict[str, Any]]) -> None:
    image = images[0] if images else None
    if not isinstance(image, dict):
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="completed")
        return
    filename = image.get("filename")
    if not isinstance(filename, str) or not filename:
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="completed")
        return
    subfolder = image.get("subfolder", "")
    image_type = image.get("type", "output")
    if not isinstance(subfolder, str) or not isinstance(image_type, str):
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="completed")
        return

    generation = get_image_generation(prompt_id, user_id)
    storage_file_id = generation.get("storage_file_id") if generation else None
    size_bytes: int | None = None
    if storage_enabled() and not storage_file_id:
        query = urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
        content, media_type = _request_bytes(f"/view?{query}")
        try:
            storage_file_id = storage_upload_file(
                content=content,
                media_type=media_type or "image/png",
                owner_id=str(user_id),
            )
            size_bytes = len(content)
        except StorageError as exc:
            update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
            raise _ComfyUIError(str(exc)) from exc

    path_parts = [image_type, subfolder, filename]
    file_path = "/".join(part for part in path_parts if part)
    update_image_generation_status(
        prompt_id=prompt_id,
        user_id=user_id,
        status="completed",
        file_path=file_path,
        storage_file_id=storage_file_id if isinstance(storage_file_id, str) else None,
        filename=filename,
        subfolder=subfolder,
        image_type=image_type,
        size_bytes=size_bytes,
    )


@router.get("/{prompt_id}/view")
def view_generated_image(
    prompt_id: str,
    filename: str = Query(min_length=1, max_length=255),
    subfolder: str = Query(default="", max_length=255),
    image_type: str = Query(default="output", alias="type", max_length=32),
    user: UserResponse = Depends(current_user),
) -> Response:
    generation = _require_owned_generation(prompt_id, user.id)
    if (
        generation["filename"] != filename
        or generation["subfolder"] != subfolder
        or generation["image_type"] != image_type
    ):
        raise HTTPException(status_code=404, detail="생성 결과 이미지를 찾을 수 없습니다.")
    storage_file_id = generation.get("storage_file_id")
    if storage_enabled() and isinstance(storage_file_id, str) and storage_file_id:
        try:
            return RedirectResponse(
                storage_read_url(file_id=storage_file_id, owner_id=str(user.id)),
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    try:
        history = _request_json("GET", f"/history/{prompt_id}")
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    entry = history.get(prompt_id)
    available_images = _raw_image_outputs(entry.get("outputs") if isinstance(entry, dict) else None)
    if not any(
        image.get("filename") == filename
        and image.get("subfolder", "") == subfolder
        and image.get("type", "output") == image_type
        for image in available_images
    ):
        raise HTTPException(status_code=404, detail="생성 결과 이미지를 찾을 수 없습니다.")

    query = urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
    try:
        content, media_type = _request_bytes(f"/view?{query}")
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return Response(content=content, media_type=media_type or "image/png")


def _image_options(model_family: ModelFamily = "anima") -> ImageGenerationOptions:
    data = _request_json("GET", "/object_info")
    if model_family == "anima":
        checkpoints = _family_choices(data, "UNETLoader", "unet_name", "Anima/")
        loras = _family_choices(data, "LoraLoaderModelOnly", "lora_name", "Anima/")
        preferred_checkpoint = "Anima/anima_aestheticV11.safetensors"
        default_cfg = 4.0
        default_steps = 30
        preferred_sampler = _DEFAULT_SAMPLER
        preferred_scheduler = _DEFAULT_SCHEDULER
    elif model_family == "moss":
        checkpoints = _family_choices(data, "UNETLoader", "unet_name", "MOSS/")
        loras = [name for name in _node_choices(data, "LoraLoaderModelOnly", "lora_name") if "moss" in name.casefold()]
        preferred_checkpoint = _MOSS_CHECKPOINT
        default_cfg, default_steps = 3.0, 50
        preferred_sampler, preferred_scheduler = "euler", "sgm_uniform"
        if _MOSS_ENCODER not in _node_choices(data, "CLIPLoader", "clip_name") or _MOSS_VAE not in _node_choices(data, "VAELoader", "vae_name"):
            raise _ComfyUIError("MOSS 텍스트 인코더 또는 VAE가 아직 설치되지 않았습니다.")
        if "moss_image" not in _node_choices(data, "CLIPLoader", "type") or "EmptyFlux2LatentImage" not in data:
            raise _ComfyUIError("MOSS 지원 ComfyUI 업데이트와 재시작이 필요합니다.")
    elif model_family in _EDIT_MODELS:
        model = _EDIT_MODELS[model_family]
        checkpoints = [name for name in _node_choices(data, "UNETLoader", "unet_name") if name == model["checkpoint"]]
        loras = []
        preferred_checkpoint = model["checkpoint"]
        default_cfg = 1.0
        default_steps = model["steps"]
        preferred_sampler = "euler"
        preferred_scheduler = model.get("scheduler", "simple")
        clip_names = _node_choices(data, "CLIPLoader", "clip_name")
        vae_names = _node_choices(data, "VAELoader", "vae_name")
        required_encoders = [model["text_encoder"]]
        if model_family == "flux3_klein":
            required_encoders.append(_FLUX3_PROMPT_UPSAMPLER)
        if any(name not in clip_names for name in required_encoders) or model["vae"] not in vae_names:
            raise _ComfyUIError("편집 모델의 텍스트 인코더 또는 VAE가 설치되지 않았습니다.")
        if any(name not in data for name in model["nodes"]):
            raise _ComfyUIError("이미지 편집에 필요한 ComfyUI 노드가 없습니다. ComfyUI를 업데이트하고 재시작해 주세요.")
    else:
        checkpoints = _family_choices(data, "CheckpointLoaderSimple", "ckpt_name", "Illustrious/")
        loras = _family_choices(data, "LoraLoader", "lora_name", "Illustrious/")
        preferred_checkpoint = "Illustrious/unholyDesireMixSinister_v80.safetensors"
        default_cfg = 4.0
        default_steps = 30
        preferred_sampler = _DEFAULT_SAMPLER
        preferred_scheduler = _DEFAULT_SCHEDULER
    samplers = _node_choices(data, "KSampler", "sampler_name")
    schedulers = _node_choices(data, "KSampler", "scheduler")
    if model_family == "qwen_image_2_1":
        samplers, schedulers = ["euler"], [_QWEN21_TURBO_SCHEDULER]
    embeddings = _installed_family_files("embeddings", f"{model_family.title()}/")
    if not checkpoints and model_family != "illustrious":
        raise _ComfyUIError(f"ComfyUI에서 {model_family.title()} 체크포인트를 찾을 수 없습니다.")
    if not samplers or not schedulers:
        raise _ComfyUIError("ComfyUI에서 sampler 또는 scheduler 목록을 찾을 수 없습니다.")
    default_checkpoint = preferred_checkpoint if preferred_checkpoint in checkpoints else next(iter(checkpoints), "")
    return ImageGenerationOptions(
        model_family=model_family,
        prompt_enhancer_available=model_family == "qwen_image_2_1" and _QWEN21_PROMPT_ENHANCER in _node_choices(data, "CLIPLoader", "clip_name") and all(name in data for name in _QWEN21_PE_NODES),
        checkpoints=checkpoints,
        loras=loras,
        embeddings=embeddings,
        samplers=samplers,
        schedulers=schedulers,
        default_checkpoint=default_checkpoint,
        default_sampler=preferred_sampler if preferred_sampler in samplers else samplers[0],
        default_scheduler=preferred_scheduler if preferred_scheduler in schedulers else schedulers[0],
        default_cfg=default_cfg,
        default_steps=default_steps,
    )


def _family_choices(
    data: dict[str, Any], node_name: str, input_name: str, prefix: str
) -> list[str]:
    return [value for value in _node_choices(data, node_name, input_name) if value.startswith(prefix)]


def _installed_family_files(category: str, prefix: str) -> list[str]:
    directory = Path(settings.comfyui_models_path) / category
    if not directory.is_dir():
        return []
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.casefold() in {".safetensors", ".pt", ".bin"}
        and path.relative_to(directory).as_posix().startswith(prefix)
    )


def _node_choices(data: dict[str, Any], node_name: str, input_name: str) -> list[str]:
    node = data.get(node_name)
    if not isinstance(node, dict):
        return []
    required = node.get("input", {}).get("required", {})
    values = required.get(input_name, []) if isinstance(required, dict) else []
    choices = values[0] if values and isinstance(values[0], list) else values[1].get("options", []) if len(values) > 1 and values[0] == "COMBO" and isinstance(values[1], dict) else []
    return sorted(value for value in choices if isinstance(value, str))


def _validate_model_choice(payload: ImageGenerationRequest, options: ImageGenerationOptions) -> None:
    family_name = {"anima": "Anima", "illustrious": "Illustrious", "flux3_klein": "FLUX 3 Klein", "moss": "MOSS", "qwen_image_2_1": "Qwen Image 2.1 Turbo"}[payload.model_family]
    if options.model_family != payload.model_family or payload.checkpoint not in options.checkpoints:
        raise HTTPException(status_code=422, detail=f"선택한 {family_name} 체크포인트를 찾을 수 없습니다.")
    lora_names = [lora.name for lora in payload.loras]
    if len(lora_names) != len(set(lora_names)):
        raise HTTPException(status_code=422, detail="같은 LoRA를 중복 선택할 수 없습니다.")
    if any(name not in options.loras for name in lora_names):
        raise HTTPException(status_code=422, detail=f"선택한 {family_name} LoRA를 찾을 수 없습니다.")
    if payload.sampler_name not in options.samplers:
        raise HTTPException(status_code=422, detail="선택한 sampler를 찾을 수 없습니다.")
    if payload.scheduler not in options.schedulers:
        raise HTTPException(status_code=422, detail="선택한 scheduler를 찾을 수 없습니다.")
    if payload.moss and payload.model_family != "moss":
        raise HTTPException(status_code=422, detail="MOSS 설정은 MOSS 모델에서만 사용할 수 있습니다.")
    if payload.model_family == "moss":
        if payload.width % 16 or payload.height % 16:
            raise HTTPException(status_code=422, detail="MOSS 이미지 가로·세로 크기는 16의 배수여야 합니다.")
        if payload.moss:
            try:
                moss_layout_prompt(_effective_positive_prompt(payload), payload.moss, payload.width, payload.height)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.model_family == "qwen_image_2_1":
        if payload.prompt_enhancement_enabled and not options.prompt_enhancer_available:
            raise HTTPException(status_code=503, detail="Qwen 프롬프트 강화 모델이 준비되지 않았습니다. 다운로드 후 사용하거나 프롬프트 강화를 꺼 주세요.")
        if payload.cfg != 1 or payload.steps != 8 or payload.sampler_name != "euler" or payload.scheduler != _QWEN21_TURBO_SCHEDULER:
            raise HTTPException(status_code=422, detail="Qwen 2.1 Turbo는 공식 8스텝·CFG 1·Euler 설정을 사용합니다.")
    if payload.model_family in _EDIT_MODELS:
        if payload.width % 32 or payload.height % 32:
            raise HTTPException(status_code=422, detail="편집 이미지 가로·세로 크기는 32의 배수여야 합니다.")
        if payload.model_family == "flux3_klein" and payload.cfg != 1:
            raise HTTPException(status_code=422, detail="FLUX 3 Klein의 CFG는 1로 설정해 주세요.")
        if isinstance(payload, ImageToImageGenerationRequest) and payload.denoise != 1:
            raise HTTPException(status_code=422, detail="참조 이미지 편집의 Denoise는 1로 설정해 주세요.")
    if payload.width % 8 or payload.height % 8:
        raise HTTPException(status_code=422, detail="이미지 가로·세로 크기는 8의 배수여야 합니다.")


def _combined_prompt(prefix: str, prompt: str, label: str) -> str:
    combined = ", ".join(value for value in (prefix.strip(), prompt.strip()) if value)
    if len(combined) > 5000:
        raise HTTPException(status_code=422, detail=f"{label}는 5,000자 이하로 입력해 주세요.")
    return combined


def _effective_positive_prompt(payload: ImageGenerationRequest) -> str:
    base_prompt = payload.prompt.strip()
    if not payload.prompt_enhancement_enabled or payload.model_family == "qwen_image_2_1":
        return _combined_prompt(payload.positive_prompt_prefix, base_prompt, "긍정 프롬프트")
    improved_prompt = (payload.improved_prompt or "").strip()
    if not improved_prompt:
        raise HTTPException(status_code=422, detail="개선된 프롬프트를 먼저 생성해 주세요.")
    return _combined_prompt(payload.positive_prompt_prefix, improved_prompt, "긍정 프롬프트")


def _effective_negative_prompt(payload: ImageGenerationRequest) -> str:
    return _combined_prompt(payload.negative_prompt_prefix, payload.negative_prompt, "부정 프롬프트")


def _build_prompt(
    payload: ImageGenerationRequest,
    *,
    input_image: str | None = None,
    denoise: float = 1.0,
    input_references: list[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], int]:
    if payload.model_family == "moss":
        if input_image or input_references or isinstance(payload, ImageToImageGenerationRequest):
            raise HTTPException(status_code=422, detail="MOSS는 T2I에서만 사용할 수 있습니다.")
        return _build_moss_prompt(payload)
    if payload.model_family in _EDIT_MODELS:
        if not input_image:
            raise HTTPException(status_code=422, detail="선택한 편집 모델에는 소스 이미지가 필요합니다.")
        if payload.model_family == "qwen_image_2_1":
            return _build_qwen21_edit_prompt(payload, input_image, input_references or [])
        return _build_edit_prompt(payload, input_image, input_references or [])
    seed = payload.seed if payload.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    positive_prompt = _effective_positive_prompt(payload)
    negative_prompt = _effective_negative_prompt(payload)
    prompt: dict[str, dict[str, Any]] = {}
    if payload.model_family == "anima":
        prompt.update(
            {
                "1": {
                    "class_type": "UNETLoader",
                    "inputs": {"unet_name": payload.checkpoint, "weight_dtype": "default"},
                },
                "3": {
                    "class_type": "CLIPLoader",
                    "inputs": {
                        "clip_name": "qwen_3_06b_base.safetensors",
                        "type": "stable_diffusion",
                        "device": "default",
                    },
                },
                "4": {
                    "class_type": "VAELoader",
                    "inputs": {"vae_name": "qwen_image_vae.safetensors"},
                },
            }
        )
        model: list[Any] = ["1", 0]
        clip: list[Any] = ["3", 0]
        vae: list[Any] = ["4", 0]
        for index, lora in enumerate(payload.loras, start=20):
            prompt[str(index)] = {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "model": model,
                    "lora_name": lora.name,
                    "strength_model": lora.strength,
                },
            }
            model = [str(index), 0]
    else:
        prompt["1"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": payload.checkpoint},
        }
        model = ["1", 0]
        clip = ["1", 1]
        vae = ["1", 2]
        for index, lora in enumerate(payload.loras, start=20):
            prompt[str(index)] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": model,
                    "clip": clip,
                    "lora_name": lora.name,
                    "strength_model": lora.strength,
                    "strength_clip": lora.strength,
                },
            }
            model = [str(index), 0]
            clip = [str(index), 1]

    prompt["5"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": positive_prompt, "clip": clip},
    }
    prompt["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": clip}}
    if input_image:
        prompt.update(
            {
                "7": {"class_type": "LoadImage", "inputs": {"image": input_image}},
                "11": {
                    "class_type": "ImageScale",
                    "inputs": {
                        "image": ["7", 0],
                        "upscale_method": "lanczos",
                        "width": payload.width,
                        "height": payload.height,
                        "crop": "disabled",
                    },
                },
                "12": {
                    "class_type": "VAEEncode",
                    "inputs": {"pixels": ["11", 0], "vae": vae},
                },
            }
        )
        latent: list[Any] = ["12", 0]
    else:
        prompt["7"] = {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": payload.width, "height": payload.height, "batch_size": 1},
        }
        latent = ["7", 0]
    prompt.update(
        {
            "8": {
                "class_type": "KSampler",
                "inputs": {
                    "model": model,
                    "seed": seed,
                    "steps": payload.steps,
                    "cfg": payload.cfg,
                    "sampler_name": payload.sampler_name,
                    "scheduler": payload.scheduler,
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "latent_image": latent,
                    "denoise": denoise,
                },
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["8", 0], "vae": vae},
            },
            "10": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": f"LocalField_{payload.model_family.title()}_{'I2I' if input_image else 'T2I'}",
                    "images": ["9", 0],
                },
            },
        }
    )
    return prompt, seed


def _build_moss_prompt(payload: ImageGenerationRequest) -> tuple[dict[str, dict[str, Any]], int]:
    seed = payload.seed if payload.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    moss = payload.moss or MossSettings()
    try:
        text = moss_layout_prompt(_effective_positive_prompt(payload), moss, payload.width, payload.height)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": payload.checkpoint, "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": _MOSS_ENCODER, "type": "moss_image", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": _MOSS_VAE}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": text}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": _effective_negative_prompt(payload)}},
        "7": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": payload.width, "height": payload.height, "batch_size": 1}},
    }
    model: list[Any] = ["1", 0]
    for index, lora in enumerate(payload.loras, start=20):
        graph[str(index)] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": lora.name, "strength_model": lora.strength}}
        model = [str(index), 0]
    graph["13"] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": model, "shift": 5.0}}
    model = ["13", 0]
    if payload.cfg > 1:
        graph["14"] = {"class_type": "SkipLayerGuidanceDiTSimple", "inputs": {"model": model, "double_layers": "", "single_layers": "22", "start_percent": 0.0, "end_percent": 1.0}}
        model = ["14", 0]
    graph["8"] = {"class_type": "KSampler", "inputs": {"model": model, "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0], "seed": seed, "steps": payload.steps, "cfg": payload.cfg, "sampler_name": payload.sampler_name, "scheduler": payload.scheduler, "denoise": 1.0}}
    graph["9"] = {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}}
    graph["10"] = {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "LocalField_MOSS_T2I"}}
    return graph, seed



def _build_qwen21_edit_prompt(payload: ImageGenerationRequest, input_image: str, input_references: list[str]) -> tuple[dict[str, dict[str, Any]], int]:
    model = _EDIT_MODELS["qwen_image_2_1"]
    seed = payload.seed if payload.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": payload.checkpoint, "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": model["text_encoder"], "type": model["clip_type"], "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": model["vae"]}},
        "7": {"class_type": "LoadImage", "inputs": {"image": input_image}},
        "11": {"class_type": "ImageScale", "inputs": {"image": ["7", 0], "upscale_method": "lanczos", "width": payload.width, "height": payload.height, "crop": "disabled"}},
        "12": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["3", 0], "vae": ["4", 0], "prompt": _effective_positive_prompt(payload), "negative_prompt": "", "resolution": 0, "images.image_1": ["11", 0]}},
        "13": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
        "14": {"class_type": "ManualSigmas", "inputs": {"sigmas": _QWEN21_TURBO_SIGMAS}},
        "15": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "16": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "CFGGuider", "inputs": {"model": ["13", 0], "positive": ["12", 0], "negative": ["12", 1], "cfg": 1.0}},
        "8": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["16", 0], "guider": ["17", 0], "sampler": ["15", 0], "sigmas": ["14", 0], "latent_image": ["12", 2]}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "LocalField_Qwen21_Turbo_R2I" if input_references else "LocalField_Qwen21_Turbo_I2I"}},
    }
    for index, filename in enumerate(input_references, start=2):
        load_id, scale_id = str(100 + index * 2), str(101 + index * 2)
        graph[load_id] = {"class_type": "LoadImage", "inputs": {"image": filename}}
        graph[scale_id] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": [load_id, 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 32}}
        graph["12"]["inputs"][f"images.image_{index}"] = [scale_id, 0]
    if payload.prompt_enhancement_enabled:
        graph["30"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": _QWEN21_PROMPT_ENHANCER, "type": "qwen_image", "device": "default"}}
        images = {}
        for index in range(1, len(input_references) + 2):
            pad_id = str(200 + index)
            graph[pad_id] = {"class_type": "ResizeAndPadImage", "inputs": {"image": graph["12"]["inputs"][f"images.image_{index}"], "target_width": 1024, "target_height": 1024, "padding_color": "white", "interpolation": "lanczos"}}
            images[f"images.image{index - 1}"] = [pad_id, 0]
        graph["32"] = {"class_type": "BatchImagesNode", "inputs": images}
        graph["31"] = {"class_type": "TextGenerate", "inputs": {
            "clip": ["30", 0], "image": ["32", 0], "prompt": _effective_positive_prompt(payload),
            "system_prompt": (Path(__file__).parent / "workflows" / "qwen21_edit_prompt_enhancer.txt").read_text(encoding="utf-8"),
            "max_length": 4096, "sampling_mode": "on", "sampling_mode.temperature": 1.0,
            "sampling_mode.top_k": 20, "sampling_mode.top_p": 0.95, "sampling_mode.min_p": 0.0,
            "sampling_mode.repetition_penalty": 1.0, "sampling_mode.seed": seed,
            "thinking": True, "use_default_template": True, "mtp": "off",
        }}
        graph["33"] = {"class_type": "StringCompare", "inputs": {"string_a": ["31", 0], "string_b": "", "mode": "Equal", "case_sensitive": True}}
        graph["34"] = {"class_type": "ComfySwitchNode", "inputs": {"switch": ["33", 0], "on_true": _effective_positive_prompt(payload), "on_false": ["31", 0]}}
        graph["12"]["inputs"]["prompt"] = ["34", 0]
    return graph, seed


def _build_edit_prompt(payload: ImageGenerationRequest, input_image: str, input_references: list[str]) -> tuple[dict[str, dict[str, Any]], int]:
    model = _EDIT_MODELS[payload.model_family]
    seed = payload.seed if payload.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    prompt = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": payload.checkpoint, "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": model["text_encoder"], "type": model["clip_type"], "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": model["vae"]}},
        "7": {"class_type": "LoadImage", "inputs": {"image": input_image}},
        "11": {"class_type": "ImageScale", "inputs": {"image": ["7", 0], "upscale_method": "lanczos", "width": payload.width, "height": payload.height, "crop": "disabled"}},
    }
    prompt["13"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": _FLUX3_PROMPT_UPSAMPLER, "type": "flux3", "device": "default"}}
    prompt["14"] = {
        "class_type": "TextGenerate",
        "inputs": {
            "clip": ["13", 0], "image": ["11", 0], "prompt": _effective_positive_prompt(payload),
            "system_prompt": (Path(__file__).parent / "workflows" / "flux3_klein_edit_upsampler.txt").read_text(encoding="utf-8"),
            "max_length": 3584, "sampling_mode": "on", "sampling_mode.temperature": 1.0,
            "sampling_mode.top_k": 1, "sampling_mode.top_p": 0.95, "sampling_mode.min_p": 0.0,
            "sampling_mode.repetition_penalty": 1.05, "sampling_mode.seed": seed,
            "thinking": False, "use_default_template": True, "mtp": "off",
        },
    }
    prompt["5"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": ["14", 0]}}
    prompt["6"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    prompt["12"] = {
        "class_type": "ReferenceMultiLatent",
        "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["4", 0], "resolution": "keep resolution", "images.image0": ["11", 0]},
    }
    if input_references:
        prompt["90"] = {"class_type": "ResizeAndPadImage", "inputs": {"image": ["11", 0], "target_width": 1024, "target_height": 1024, "padding_color": "white", "interpolation": "lanczos"}}
        batch_images = {"images.image0": ["90", 0]}
        for index, filename in enumerate(input_references, start=1):
            load_id, scale_id, pad_id = str(100 + index * 3), str(101 + index * 3), str(102 + index * 3)
            prompt[load_id] = {"class_type": "LoadImage", "inputs": {"image": filename}}
            prompt[scale_id] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": [load_id, 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 32}}
            prompt[pad_id] = {"class_type": "ResizeAndPadImage", "inputs": {"image": [scale_id, 0], "target_width": 1024, "target_height": 1024, "padding_color": "white", "interpolation": "lanczos"}}
            prompt["12"]["inputs"][f"images.image{index}"] = [scale_id, 0]
            batch_images[f"images.image{index}"] = [pad_id, 0]
        prompt["15"] = {"class_type": "BatchImagesNode", "inputs": batch_images}
        prompt["14"]["inputs"]["image"] = ["15", 0]
    positive, negative, latent = ["12", 0], ["12", 1], ["12", 2]
    prompt["8"] = {
        "class_type": "KSampler",
        "inputs": {"model": ["1", 0], "seed": seed, "steps": payload.steps, "cfg": payload.cfg, "sampler_name": payload.sampler_name, "scheduler": payload.scheduler, "positive": positive, "negative": negative, "latent_image": latent, "denoise": 1.0},
    }
    prompt["9"] = {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}}
    prompt["10"] = {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": f"LocalField_{payload.model_family}_I2I"}}
    return prompt, seed


def _stored_image_outputs(generation: dict[str, Any], user_id: uuid.UUID) -> list[ImageOutput]:
    filename = generation.get("filename")
    if not isinstance(filename, str) or not filename:
        return []
    subfolder = generation.get("subfolder", "")
    image_type = generation.get("image_type", "output")
    if not isinstance(subfolder, str) or not isinstance(image_type, str):
        return []
    storage_file_id = generation.get("storage_file_id")
    if storage_enabled() and isinstance(storage_file_id, str) and storage_file_id:
        url = storage_read_url(file_id=storage_file_id, owner_id=str(user_id))
    else:
        url = _legacy_image_url(generation["prompt_id"], filename, subfolder, image_type)
    return [ImageOutput(url=url, filename=filename, subfolder=subfolder, type=image_type)]


def _image_outputs(prompt_id: str, user_id: uuid.UUID, outputs: Any) -> list[ImageOutput]:
    result = []
    generation = get_image_generation(prompt_id, user_id)
    storage_file_id = generation.get("storage_file_id") if generation else None
    storage_url = None
    if storage_enabled() and isinstance(storage_file_id, str) and storage_file_id:
        try:
            storage_url = storage_read_url(file_id=storage_file_id, owner_id=str(user_id))
        except StorageError as exc:
            raise _ComfyUIError(str(exc)) from exc

    for index, image in enumerate(_raw_image_outputs(outputs)):
        filename = image.get("filename")
        subfolder = image.get("subfolder", "")
        image_type = image.get("type", "output")
        if not isinstance(filename, str):
            continue
        result.append(
            ImageOutput(
                url=storage_url if index == 0 and storage_url else _legacy_image_url(prompt_id, filename, subfolder, image_type),
                filename=filename,
                subfolder=subfolder,
                type=image_type,
            )
        )
    return result


def _legacy_image_url(prompt_id: str, filename: str, subfolder: str, image_type: str) -> str:
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
    return f"/generation/image/{prompt_id}/view?{query}"


def _raw_image_outputs(outputs: Any) -> list[dict[str, Any]]:
    if not isinstance(outputs, dict):
        return []
    images = []
    for output in outputs.values():
        if isinstance(output, dict) and isinstance(output.get("images"), list):
            images.extend(image for image in output["images"] if isinstance(image, dict))
    return images


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = UrlRequest(
        _comfy_url(path),
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=_COMFYUI_TIMEOUT_SECONDS) as response:
            decoded = json.loads(response.read())
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("ComfyUI에 연결할 수 없습니다.") from exc
    if not isinstance(decoded, dict):
        raise _ComfyUIError("ComfyUI 응답 형식이 올바르지 않습니다.")
    return decoded


def cancel_comfy_generation(prompt_id: str) -> bool:
    response = _request_json("POST", f"/api/jobs/{prompt_id}/cancel")
    return response.get("cancelled") is True


def _request_bytes(path: str) -> tuple[bytes, str | None]:
    request = UrlRequest(_comfy_url(path), method="GET")
    try:
        with urlopen(request, timeout=_COMFYUI_TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get_content_type()
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 이미지 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError) as exc:
        raise _ComfyUIError("ComfyUI 이미지에 연결할 수 없습니다.") from exc


def _enhance_prompt(prompt: str, model_family: ModelFamily = "anima") -> PromptEnhancementResponse:
    if model_family == "moss":
        raise HTTPException(status_code=422, detail="MOSS는 입력한 장면 설명과 레이아웃을 직접 사용합니다.")
    if model_family == "qwen_image_2_1":
        raise HTTPException(status_code=422, detail="Qwen 프롬프트 강화는 생성 시 원본·참조 이미지와 함께 실행됩니다.")
    prompt = prompt.strip()
    if model_family in _EDIT_MODELS:
        return PromptEnhancementResponse(
            improved_prompt=PromptEnhancementContent(
                contents=_request_structured_content(
                    system_prompt=IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
                    user_prompt=IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT.format(prompt=prompt),
                    max_tokens=768,
                    temperature=0.6,
                )
            )
        )
    candidate_tags = search_danbooru_tags(prompt, limit=96)
    natural_language = (
        _request_structured_content(
            system_prompt=IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
            user_prompt=IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT.format(prompt=prompt),
            max_tokens=768,
            temperature=0.6,
        )
        if model_family == "anima"
        else ""
    )
    raw_tags = _request_structured_content(
        system_prompt=IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT,
        user_prompt=IMAGE_PROMPT_ENHANCEMENT_TAG_USER_PROMPT.format(
            prompt=prompt,
            candidate_tags=", ".join(candidate_tags),
        ),
        max_tokens=256,
        temperature=0.6,
    )
    valid_tags = validate_danbooru_tags(raw_tags)
    if not valid_tags:
        valid_tags = candidate_tags[:24]
    if not valid_tags:
        raise DanbooruError("사용할 Danbooru 태그를 찾지 못했습니다.")
    improved_prompt = ", ".join(valid_tags if model_family == "illustrious" else (*valid_tags, natural_language))
    return PromptEnhancementResponse(
        improved_prompt=PromptEnhancementContent(contents=improved_prompt[:5000]),
    )


def _request_structured_content(
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    pattern: str = r"^[A-Za-z0-9 ,'-]+$",
) -> str:
    parsed = _request_structured_object(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        schema={
            "type": "object",
            "properties": {
                "contents": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 5000,
                    "pattern": pattern,
                }
            },
            "required": ["contents"],
            "additionalProperties": False,
        },
        name="prompt_contents",
    )
    contents = parsed.get("contents")
    if not isinstance(contents, str) or not contents.strip():
        raise _VLLMError("vLLM 구조화 응답의 contents가 비어 있습니다.")
    contents = contents.strip()
    if not re.fullmatch(pattern, contents):
        raise _VLLMError("vLLM 프롬프트 결과에 허용되지 않은 문자가 포함되어 있습니다.")
    return contents[:5000]


def _request_structured_object(
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    schema: dict[str, Any],
    name: str,
    timeout_seconds: int = _VLLM_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    response = _request_vllm_json(
        {
            "model": settings.vllm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "schema": schema,
                    "strict": True,
                },
            },
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout_seconds=timeout_seconds,
    )
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise _VLLMError("vLLM이 구조화된 프롬프트 결과를 반환하지 않았습니다.", provider_response=response)
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        message = choice.get("message")
        raw_content = message.get("content") if isinstance(message, dict) else None
        content = raw_content if isinstance(raw_content, str) else ""
        try:
            parsed_content = json.loads(content.strip())
        except json.JSONDecodeError:
            parsed_content = None
        properties = schema.get("properties")
        known_fields = set(properties) if isinstance(properties, dict) else set()
        shots_schema = properties.get("shots") if isinstance(properties, dict) else None
        shot_properties = shots_schema.get("items", {}).get("properties") if isinstance(shots_schema, dict) and isinstance(shots_schema.get("items"), dict) else None
        if isinstance(shot_properties, dict):
            known_fields.update(shot_properties)
        json_keys = re.findall(r'"([^"\\]+)"\s*:', content)
        last_field = next((key for key in reversed(json_keys) if key in known_fields), None)
        usage = response.get("usage")
        completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        shot_count = len(parsed_content.get("shots", [])) if isinstance(parsed_content, dict) and isinstance(parsed_content.get("shots"), list) else None
        logger.warning(
            "vllm_structured_length name=%s max_tokens=%s completion_tokens=%s raw_characters=%s json_complete=%s trailing_whitespace_characters=%s last_field=%s shot_count=%s",
            name,
            max_tokens,
            completion_tokens,
            len(content),
            isinstance(parsed_content, dict),
            len(content) - len(content.rstrip()),
            last_field,
            shot_count,
        )
        raise _VLLMError("vLLM 프롬프트 결과가 길이 제한으로 중단되었습니다.", provider_response=response)
    message = choice.get("message")
    raw_content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(raw_content, str):
        raise _VLLMError("vLLM 구조화 응답 형식이 올바르지 않습니다.", provider_response=response)
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content.strip(), flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise _VLLMError("vLLM 구조화 응답을 JSON으로 읽을 수 없습니다.", provider_response=response) from exc
    if not isinstance(parsed, dict):
        raise _VLLMError("vLLM 구조화 응답이 JSON 객체가 아닙니다.", provider_response=response)
    return parsed


def _request_vllm_json(payload: dict[str, Any], *, timeout_seconds: int = _VLLM_TIMEOUT_SECONDS) -> dict[str, Any]:
    request = UrlRequest(
        _vllm_url("/v1/chat/completions"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read())
    except UrlHTTPError as exc:
        raise _VLLMError(f"vLLM 프롬프트 강화 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _VLLMError("vLLM에 연결할 수 없습니다.") from exc
    if not isinstance(decoded, dict):
        raise _VLLMError("vLLM 응답 형식이 올바르지 않습니다.")
    return decoded


def _comfy_url(path: str) -> str:
    return f"{settings.comfyui_url.rstrip('/')}/{path.lstrip('/')}"


def _vllm_url(path: str) -> str:
    return f"{settings.vllm_url.rstrip('/')}/{path.lstrip('/')}"


class _ComfyUIError(RuntimeError):
    pass


class _VLLMError(RuntimeError):
    def __init__(self, message: str, *, provider_response: dict[str, Any] | None = None):
        super().__init__(message)
        self.provider_response = provider_response
