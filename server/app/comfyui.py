from __future__ import annotations

import asyncio
from datetime import datetime
import json
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

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse, StreamingResponse

from .auth import UserResponse, current_user
from .configs.constants import settings
from .danbooru import DanbooruError, search_danbooru_tags, validate_danbooru_tags
from .database import (
    create_image_generation as create_image_generation_record,
    generation_elapsed_seconds,
    get_image_generation,
    update_image_generation_status,
)
from .generation_events import generation_event_broker, generation_key
from .prompts import (
    IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_TAG_USER_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT,
)
from .storage import StorageError, enabled as storage_enabled, read_url as storage_read_url, upload_file as storage_upload_file


router = APIRouter(prefix="/generation/image", tags=["image generation"])
_DEFAULT_NEGATIVE_PROMPT = "worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia"
_COMFYUI_TIMEOUT_SECONDS = 30
_VLLM_TIMEOUT_SECONDS = 600
_SSE_HEARTBEAT_SECONDS = 15
_MAX_SEED = 2**63 - 1
_DEFAULT_SAMPLER = "er_sde"
_DEFAULT_SCHEDULER = "simple"
_PROGRESS_UNSET = object()
_progress_lock = threading.Lock()
_progress_states: dict[str, dict[str, Any]] = {}


class LoraSelection(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    strength: float = Field(default=1.0)


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    prompt_enhancement_enabled: bool = False
    improved_prompt: str | None = Field(default=None, max_length=5000)
    negative_prompt: str = Field(default=_DEFAULT_NEGATIVE_PROMPT, max_length=5000)
    checkpoint: str = Field(min_length=1, max_length=255)
    loras: list[LoraSelection] = Field(default_factory=list, max_length=8)
    cfg: float = Field(default=4, ge=0, le=20)
    steps: int = Field(default=30, ge=1, le=100)
    sampler_name: str = Field(default=_DEFAULT_SAMPLER, min_length=1, max_length=64)
    scheduler: str = Field(default=_DEFAULT_SCHEDULER, min_length=1, max_length=64)
    width: int = Field(default=1024, ge=64, le=2048)
    height: int = Field(default=1024, ge=64, le=2048)
    seed: int | None = Field(default=None, ge=0, le=_MAX_SEED)


class ImageGenerationOptions(BaseModel):
    checkpoints: list[str]
    loras: list[str]
    samplers: list[str]
    schedulers: list[str]
    default_checkpoint: str
    default_sampler: str
    default_scheduler: str


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


def _set_progress_state(
    prompt_id: str,
    user_id: uuid.UUID,
    *,
    status: Any = _PROGRESS_UNSET,
    progress: Any = _PROGRESS_UNSET,
    queue_position: Any = _PROGRESS_UNSET,
) -> bool:
    key = _progress_key(prompt_id, user_id)
    with _progress_lock:
        state = _progress_states.setdefault(key, {"status": None, "progress": 0.0, "queue_position": None})
        previous = state.copy()
        if status is not _PROGRESS_UNSET:
            state["status"] = status
        if progress is not _PROGRESS_UNSET:
            state["progress"] = max(0.0, min(100.0, float(progress)))
        if queue_position is not _PROGRESS_UNSET:
            state["queue_position"] = queue_position
        return state != previous


def record_comfy_progress(
    prompt_id: str,
    user_id: uuid.UUID,
    event_name: str,
    data: dict[str, Any],
) -> bool:
    event_prompt_id = data.get("prompt_id")
    if event_prompt_id is not None and event_prompt_id != prompt_id:
        return False
    if event_name == "execution_start":
        return _set_progress_state(prompt_id, user_id, status="processing", progress=0, queue_position=None)
    if event_name == "executing":
        if data.get("node") is None:
            return False
        return _set_progress_state(prompt_id, user_id, status="processing", queue_position=None)
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
    prompt: str = Field(min_length=1, max_length=5000)


class PromptEnhancementContent(BaseModel):
    contents: str = Field(min_length=1, max_length=5000)


class PromptEnhancementResponse(BaseModel):
    improved_prompt: PromptEnhancementContent


@router.get("/options", response_model=ImageGenerationOptions)
def image_options(_: UserResponse = Depends(current_user)) -> ImageGenerationOptions:
    try:
        return _image_options()
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/enhance-prompt", response_model=PromptEnhancementResponse)
def enhance_prompt(
    payload: PromptEnhancementRequest,
    _: UserResponse = Depends(current_user),
) -> PromptEnhancementResponse:
    try:
        return _enhance_prompt(payload.prompt)
    except (DanbooruError, _VLLMError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("", response_model=ImageGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_image_generation(
    payload: ImageGenerationRequest,
    user: UserResponse = Depends(current_user),
) -> ImageGenerationAccepted:
    try:
        options = _image_options()
        _validate_model_choice(payload, options)
        prompt, seed = _build_prompt(payload)
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
        prompt=_effective_positive_prompt(payload),
        negative_prompt=payload.negative_prompt,
        checkpoint=payload.checkpoint,
        loras=[lora.model_dump() for lora in payload.loras],
        cfg=payload.cfg,
        steps=payload.steps,
        sampler_name=payload.sampler_name,
        scheduler=payload.scheduler,
        width=payload.width,
        height=payload.height,
        seed=seed,
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


def _image_options() -> ImageGenerationOptions:
    data = _request_json("GET", "/object_info")
    checkpoints = _anima_choices(data, "UNETLoader", "unet_name")
    loras = _anima_choices(data, "LoraLoaderModelOnly", "lora_name")
    samplers = _node_choices(data, "KSampler", "sampler_name")
    schedulers = _node_choices(data, "KSampler", "scheduler")
    if not checkpoints:
        raise _ComfyUIError("ComfyUI에서 Anima 체크포인트를 찾을 수 없습니다.")
    if not samplers or not schedulers:
        raise _ComfyUIError("ComfyUI에서 sampler 또는 scheduler 목록을 찾을 수 없습니다.")
    default_checkpoint = (
        "Anima/anima_aestheticV11.safetensors"
        if "Anima/anima_aestheticV11.safetensors" in checkpoints
        else checkpoints[0]
    )
    return ImageGenerationOptions(
        checkpoints=checkpoints,
        loras=loras,
        samplers=samplers,
        schedulers=schedulers,
        default_checkpoint=default_checkpoint,
        default_sampler=_DEFAULT_SAMPLER if _DEFAULT_SAMPLER in samplers else samplers[0],
        default_scheduler=_DEFAULT_SCHEDULER if _DEFAULT_SCHEDULER in schedulers else schedulers[0],
    )


def _anima_choices(data: dict[str, Any], node_name: str, input_name: str) -> list[str]:
    return [value for value in _node_choices(data, node_name, input_name) if value.startswith("Anima/")]


def _node_choices(data: dict[str, Any], node_name: str, input_name: str) -> list[str]:
    node = data.get(node_name)
    if not isinstance(node, dict):
        return []
    required = node.get("input", {}).get("required", {})
    values = required.get(input_name, []) if isinstance(required, dict) else []
    choices = values[0] if values and isinstance(values[0], list) else []
    return sorted(value for value in choices if isinstance(value, str))


def _validate_model_choice(payload: ImageGenerationRequest, options: ImageGenerationOptions) -> None:
    if payload.checkpoint not in options.checkpoints:
        raise HTTPException(status_code=422, detail="선택한 Anima 체크포인트를 찾을 수 없습니다.")
    lora_names = [lora.name for lora in payload.loras]
    if len(lora_names) != len(set(lora_names)):
        raise HTTPException(status_code=422, detail="같은 LoRA를 중복 선택할 수 없습니다.")
    if any(name not in options.loras for name in lora_names):
        raise HTTPException(status_code=422, detail="선택한 Anima LoRA를 찾을 수 없습니다.")
    if payload.sampler_name not in options.samplers:
        raise HTTPException(status_code=422, detail="선택한 sampler를 찾을 수 없습니다.")
    if payload.scheduler not in options.schedulers:
        raise HTTPException(status_code=422, detail="선택한 scheduler를 찾을 수 없습니다.")
    if payload.width % 8 or payload.height % 8:
        raise HTTPException(status_code=422, detail="이미지 가로·세로 크기는 8의 배수여야 합니다.")


def _effective_positive_prompt(payload: ImageGenerationRequest) -> str:
    base_prompt = payload.prompt.strip()
    if not payload.prompt_enhancement_enabled:
        return base_prompt
    improved_prompt = (payload.improved_prompt or "").strip()
    if not improved_prompt:
        raise HTTPException(status_code=422, detail="개선된 프롬프트를 먼저 생성해 주세요.")
    return improved_prompt


def _build_prompt(payload: ImageGenerationRequest) -> tuple[dict[str, dict[str, Any]], int]:
    seed = payload.seed if payload.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    positive_prompt = _effective_positive_prompt(payload)
    model: list[Any] = ["1", 0]
    prompt: dict[str, dict[str, Any]] = {
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
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive_prompt, "clip": ["3", 0]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": payload.negative_prompt, "clip": ["3", 0]},
        },
        "7": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": payload.width, "height": payload.height, "batch_size": 1},
        },
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
                "latent_image": ["7", 0],
                "denoise": 1.0,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["4", 0]},
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "LocalField_Anima", "images": ["9", 0]},
        },
    }
    for index, lora in enumerate(payload.loras, start=11):
        prompt[str(index)] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": model,
                "lora_name": lora.name,
                "strength_model": lora.strength,
            },
        }
        model = [str(index), 0]
    prompt["8"]["inputs"]["model"] = model
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


def _request_action(method: str, path: str, payload: dict[str, Any] | None = None) -> None:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = UrlRequest(
        _comfy_url(path),
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=_COMFYUI_TIMEOUT_SECONDS):
            return
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 작업 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError) as exc:
        raise _ComfyUIError("ComfyUI 작업 요청에 연결할 수 없습니다.") from exc


def cancel_comfy_generation(prompt_id: str) -> bool:
    queue = _request_json("GET", "/queue")
    running = queue.get("queue_running", [])
    if any(isinstance(item, (list, tuple)) and len(item) > 1 and item[1] == prompt_id for item in running):
        _request_action("POST", "/interrupt", {"prompt_id": prompt_id})
        return True
    pending = queue.get("queue_pending", [])
    if any(isinstance(item, (list, tuple)) and len(item) > 1 and item[1] == prompt_id for item in pending):
        _request_action("POST", "/queue", {"delete": [prompt_id]})
        return True
    return False


def _request_bytes(path: str) -> tuple[bytes, str | None]:
    request = UrlRequest(_comfy_url(path), method="GET")
    try:
        with urlopen(request, timeout=_COMFYUI_TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get_content_type()
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 이미지 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError) as exc:
        raise _ComfyUIError("ComfyUI 이미지에 연결할 수 없습니다.") from exc


def _enhance_prompt(prompt: str) -> PromptEnhancementResponse:
    prompt = prompt.strip()
    candidate_tags = search_danbooru_tags(prompt, limit=96)
    natural_language = _request_structured_content(
        system_prompt=IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
        user_prompt=IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT.format(prompt=prompt),
        max_tokens=768,
        temperature=0.8,
    )
    raw_tags = _request_structured_content(
        system_prompt=IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT,
        user_prompt=IMAGE_PROMPT_ENHANCEMENT_TAG_USER_PROMPT.format(
            prompt=prompt,
            candidate_tags=", ".join(candidate_tags),
        ),
        max_tokens=256,
        temperature=0.8,
    )
    valid_tags = validate_danbooru_tags(raw_tags)
    if not valid_tags:
        valid_tags = candidate_tags[:24]
    if not valid_tags:
        raise DanbooruError("사용할 Danbooru 태그를 찾지 못했습니다.")
    improved_prompt = ", ".join((", ".join(valid_tags), natural_language))
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
        }
    )
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise _VLLMError("vLLM이 구조화된 프롬프트 결과를 반환하지 않았습니다.")
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise _VLLMError("vLLM 프롬프트 결과가 길이 제한으로 중단되었습니다.")
    message = choice.get("message")
    raw_content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(raw_content, str):
        raise _VLLMError("vLLM 구조화 응답 형식이 올바르지 않습니다.")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content.strip(), flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise _VLLMError("vLLM 구조화 응답을 JSON으로 읽을 수 없습니다.") from exc
    if not isinstance(parsed, dict):
        raise _VLLMError("vLLM 구조화 응답이 JSON 객체가 아닙니다.")
    return parsed


def _request_vllm_json(payload: dict[str, Any]) -> dict[str, Any]:
    request = UrlRequest(
        _vllm_url("/v1/chat/completions"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_VLLM_TIMEOUT_SECONDS) as response:
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
    pass
