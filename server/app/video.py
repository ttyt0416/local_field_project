from __future__ import annotations

import asyncio
import copy
import json
import mimetypes
import re
import secrets
import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import StreamingResponse

from .auth import UserResponse, current_user
from .comfyui import _ComfyUIError, _comfy_url, _request_bytes, _request_json
from .database import (
    create_media_asset,
    create_video_generation,
    get_reusable_media,
    get_video_generation,
    update_video_generation_status,
)
from .storage import (
    StorageError,
    download_file as storage_download_file,
    enabled as storage_enabled,
    read_url as storage_read_url,
    upload_file as storage_upload_file,
)


router = APIRouter(prefix="/generation/video", tags=["video generation"])
_WORKFLOW_DIR = Path(__file__).with_name("workflows")
_ALLOWED_MODES = {"i2v", "fl2v", "r2v"}
_MAX_SEED = 2**63 - 1
_MAX_INPUT_SIZE = 50 * 1024 * 1024
_FILE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class VideoAsset(BaseModel):
    kind: Literal["image", "audio", "video"]
    file_id: str | None = Field(default=None, max_length=64)
    file_index: int | None = Field(default=None, ge=0, le=20)


class VideoGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    width: int = Field(default=1344, ge=32, le=1344)
    height: int = Field(default=768, ge=32, le=1344)
    duration: float = Field(default=5, ge=1, le=15)
    seed: int | None = Field(default=None, ge=0, le=_MAX_SEED)
    first_frame: VideoAsset | None = None
    last_frame: VideoAsset | None = None
    reference_images: list[VideoAsset] = Field(default_factory=list, max_length=9)
    reference_videos: list[VideoAsset] = Field(default_factory=list, max_length=3)
    reference_audios: list[VideoAsset] = Field(default_factory=list, max_length=3)


class VideoGenerationAccepted(BaseModel):
    prompt_id: str
    client_id: str
    generation_id: str
    mode: str
    status: Literal["queued"]


class VideoOutput(BaseModel):
    url: str
    filename: str
    subfolder: str
    type: str


class VideoGenerationStatus(BaseModel):
    prompt_id: str
    mode: str
    status: str
    video: VideoOutput | None = None


class _ResolvedAsset:
    def __init__(self, *, file_id: str, filename: str, content: bytes, media_type: str, kind: str):
        self.file_id = file_id
        self.filename = filename
        self.content = content
        self.media_type = media_type
        self.kind = kind


@router.post("/{mode}", response_model=VideoGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_video(
    mode: Literal["i2v", "fl2v", "r2v"],
    payload: str = Form(...),
    files: list[UploadFile] = File(default_factory=list),
    user: UserResponse = Depends(current_user),
) -> VideoGenerationAccepted:
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    try:
        request = VideoGenerationRequest.model_validate_json(payload)
        _validate_request(mode, request, files)
        resolved = await _resolve_assets(mode, request, files, user)
        prompt, seed = _build_prompt(mode, request, resolved)
        client_id = str(uuid.uuid4())
        response = _request_json("POST", "/prompt", {"prompt": prompt, "client_id": client_id})
    except (StorageError, _ComfyUIError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="영상 생성 입력 JSON이 올바르지 않습니다.") from exc

    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise HTTPException(status_code=502, detail="ComfyUI가 영상 생성 작업 ID를 반환하지 않았습니다.")
    input_file_ids = list(dict.fromkeys(asset.file_id for asset in resolved.values()))
    generation_id = create_video_generation(
        user_id=user.id,
        prompt_id=prompt_id,
        client_id=client_id,
        mode=mode,
        prompt=request.prompt.strip(),
        width=request.width,
        height=request.height,
        length=_frame_length(request.duration),
        seed=seed,
        input_file_ids=input_file_ids,
    )
    return VideoGenerationAccepted(
        prompt_id=prompt_id,
        client_id=client_id,
        generation_id=str(generation_id),
        mode=mode,
        status="queued",
    )


@router.get("/{mode}/{prompt_id}", response_model=VideoGenerationStatus)
def video_status(
    mode: Literal["i2v", "fl2v", "r2v"],
    prompt_id: str,
    user: UserResponse = Depends(current_user),
) -> VideoGenerationStatus:
    generation = get_video_generation(prompt_id, user.id)
    if generation is None or generation["mode"] != mode:
        raise HTTPException(status_code=404, detail="영상 생성 결과를 찾을 수 없습니다.")
    try:
        return _history_status(generation, user.id)
    except (StorageError, _ComfyUIError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/{mode}/{prompt_id}/events")
async def video_generation_events(
    mode: Literal["i2v", "fl2v", "r2v"],
    prompt_id: str,
    client_id: str = Query(min_length=1, max_length=128),
    user: UserResponse = Depends(current_user),
) -> StreamingResponse:
    generation = get_video_generation(prompt_id, user.id)
    if generation is None or generation["mode"] != mode or generation["client_id"] != client_id:
        raise HTTPException(status_code=404, detail="영상 생성 결과를 찾을 수 없습니다.")
    return StreamingResponse(
        _stream_video_events(prompt_id, mode, user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_video_events(prompt_id: str, mode: str, user_id: uuid.UUID):
    last_status: str | None = None
    heartbeat_ticks = 0
    while True:
        generation = await asyncio.to_thread(get_video_generation, prompt_id, user_id)
        if generation is None or generation["mode"] != mode:
            yield _sse_message("failed", {"prompt_id": prompt_id, "status": "failed", "message": "영상 생성 결과를 찾을 수 없습니다."})
            return

        current_status = str(generation["status"])
        if current_status != last_status:
            if current_status == "completed":
                try:
                    video = await asyncio.to_thread(_video_output, generation, user_id)
                except StorageError as exc:
                    yield _sse_message("error", {"prompt_id": prompt_id, "message": str(exc)})
                    return
                yield _sse_message(
                    "completed",
                    VideoGenerationStatus(prompt_id=prompt_id, mode=mode, status="completed", video=video).model_dump(),
                )
                return
            if current_status == "failed":
                yield _sse_message("failed", {"prompt_id": prompt_id, "mode": mode, "status": "failed"})
                return
            yield _sse_message("status", {"prompt_id": prompt_id, "mode": mode, "status": current_status})
            last_status = current_status
            heartbeat_ticks = 0
        else:
            heartbeat_ticks += 1
            if heartbeat_ticks >= 8:
                yield ": keep-alive\n\n"
                heartbeat_ticks = 0
        await asyncio.sleep(2)


def _sse_message(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _validate_request(mode: str, request: VideoGenerationRequest, files: list[UploadFile]) -> None:
    if mode not in _ALLOWED_MODES:
        raise HTTPException(status_code=404, detail="지원하지 않는 영상 생성 방식입니다.")
    assets = _request_assets(mode, request)
    if len(files) > 20:
        raise HTTPException(status_code=422, detail="영상 입력 파일은 한 번에 20개까지 선택할 수 있습니다.")
    for asset in assets:
        if (asset.file_id is None) == (asset.file_index is None):
            raise HTTPException(status_code=422, detail="각 콘텐츠는 Storage file_id 또는 새 파일 index 중 하나가 필요합니다.")
        if asset.file_index is not None:
            if asset.file_index >= len(files):
                raise HTTPException(status_code=422, detail="선택한 새 파일을 찾을 수 없습니다.")
            upload = files[asset.file_index]
            content_type = (upload.content_type or "").lower()
            if not content_type.startswith(f"{asset.kind}/"):
                raise HTTPException(status_code=415, detail=f"{asset.kind} 콘텐츠 형식이 올바르지 않습니다.")
        elif not _FILE_ID_PATTERN.fullmatch(asset.file_id or ""):
            raise HTTPException(status_code=422, detail="Storage file_id 형식이 올바르지 않습니다.")


def _request_assets(mode: str, request: VideoGenerationRequest) -> list[VideoAsset]:
    if mode == "i2v":
        if request.first_frame is None or request.first_frame.kind != "image":
            raise HTTPException(status_code=422, detail="I2V에는 시작 이미지가 필요합니다.")
        if request.last_frame is not None or request.reference_images or request.reference_videos or request.reference_audios:
            raise HTTPException(status_code=422, detail="I2V 입력 구성이 올바르지 않습니다.")
        return [request.first_frame]
    if mode == "fl2v":
        if (
            request.first_frame is None
            or request.last_frame is None
            or request.first_frame.kind != "image"
            or request.last_frame.kind != "image"
        ):
            raise HTTPException(status_code=422, detail="FL2V에는 첫 프레임과 마지막 프레임이 필요합니다.")
        if request.reference_images or request.reference_videos or request.reference_audios:
            raise HTTPException(status_code=422, detail="FL2V 입력 구성이 올바르지 않습니다.")
        return [request.first_frame, request.last_frame]
    if request.first_frame is not None or request.last_frame is not None:
        raise HTTPException(status_code=422, detail="R2V는 reference 콘텐츠를 사용합니다.")
    if any(asset.kind != "image" for asset in request.reference_images):
        raise HTTPException(status_code=422, detail="R2V reference 이미지 구성이 올바르지 않습니다.")
    if any(asset.kind != "video" for asset in request.reference_videos):
        raise HTTPException(status_code=422, detail="R2V reference 동영상 구성이 올바르지 않습니다.")
    if any(asset.kind != "audio" for asset in request.reference_audios):
        raise HTTPException(status_code=422, detail="R2V reference 오디오 구성이 올바르지 않습니다.")
    if not request.reference_images and not request.reference_videos and not request.reference_audios:
        raise HTTPException(status_code=422, detail="R2V에는 reference 이미지·동영상 또는 오디오가 필요합니다.")
    return [*request.reference_images, *request.reference_videos, *request.reference_audios]


async def _resolve_assets(
    mode: str,
    request: VideoGenerationRequest,
    files: list[UploadFile],
    user: UserResponse,
) -> dict[str, _ResolvedAsset]:
    resolved: dict[str, _ResolvedAsset] = {}
    for asset in _request_assets(mode, request):
        cache_key = _asset_cache_key(asset)
        if cache_key in resolved:
            continue
        if asset.file_id:
            record = get_reusable_media(asset.file_id, user.id)
            if record is None or record["media_kind"] != asset.kind:
                raise HTTPException(status_code=404, detail="선택한 콘텐츠를 찾을 수 없습니다.")
            content, stored_type = storage_download_file(file_id=asset.file_id, owner_id=str(user.id))
            resolved[cache_key] = _ResolvedAsset(
                file_id=asset.file_id,
                filename=record["filename"],
                content=content,
                media_type=record["content_type"] or stored_type,
                kind=asset.kind,
            )
            create_media_asset(
                user_id=user.id,
                storage_file_id=asset.file_id,
                filename=record["filename"],
                content_type=record["content_type"] or stored_type,
                media_kind=asset.kind,
                size=len(content),
            )
            continue
        upload = files[asset.file_index or 0]
        content = await upload.read(_MAX_INPUT_SIZE + 1)
        if len(content) > _MAX_INPUT_SIZE:
            raise HTTPException(status_code=413, detail="전송할 파일의 크기가 너무 큽니다.")
        if not content:
            raise HTTPException(status_code=422, detail="빈 파일은 사용할 수 없습니다.")
        filename = _safe_filename(upload.filename, asset.kind, upload.content_type)
        media_type = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        file_id = storage_upload_file(content=content, media_type=media_type, owner_id=str(user.id))
        create_media_asset(
            user_id=user.id,
            storage_file_id=file_id,
            filename=filename,
            content_type=media_type,
            media_kind=asset.kind,
            size=len(content),
        )
        resolved[cache_key] = _ResolvedAsset(
            file_id=file_id,
            filename=filename,
            content=content,
            media_type=media_type,
            kind=asset.kind,
        )
    return resolved


def _build_prompt(mode: str, request: VideoGenerationRequest, resolved: dict[str, _ResolvedAsset]) -> tuple[dict[str, dict[str, Any]], int]:
    try:
        with (_WORKFLOW_DIR / f"video_{mode}.json").open(encoding="utf-8") as handle:
            prompt = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise _ComfyUIError(f"{mode} 영상 workflow를 읽을 수 없습니다.") from exc
    prompt = copy.deepcopy(prompt)
    seed = request.seed if request.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    for node in prompt.values():
        if isinstance(node, dict) and isinstance(node.get("inputs"), dict):
            inputs = node["inputs"]
            if "prompt" in inputs and node.get("class_type") in {"MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"}:
                inputs["prompt"] = request.prompt.strip()
            if node.get("class_type") == "RandomNoise":
                inputs["noise_seed"] = seed
            if node.get("class_type") in {"MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"}:
                inputs["width"] = _multiple_of_32(request.width)
                inputs["height"] = _multiple_of_32(request.height)
                inputs["length"] = _frame_length(request.duration)
    if mode == "i2v":
        prompt["10"]["inputs"]["image"] = _upload_to_comfy(resolved, request.first_frame, "image")
    elif mode == "fl2v":
        prompt["10"]["inputs"]["image"] = _upload_to_comfy(resolved, request.first_frame, "image")
        prompt["11"]["inputs"]["image"] = _upload_to_comfy(resolved, request.last_frame, "image")
    else:
        for index, asset in enumerate(request.reference_images):
            prompt[str(100 + index)] = {
                "class_type": "LoadImage",
                "inputs": {"image": _upload_to_comfy(resolved, asset, "image")},
            }
            prompt["5"]["inputs"][f"ref_images.ref_image_{index}"] = [str(100 + index), 0]
        for index, asset in enumerate(request.reference_videos):
            video_node_id = str(300 + index)
            components_node_id = str(400 + index)
            prompt[video_node_id] = {
                "class_type": "LoadVideo",
                "inputs": {"file": _upload_to_comfy(resolved, asset, "video")},
            }
            prompt[components_node_id] = {
                "class_type": "GetVideoComponents",
                "inputs": {"video": [video_node_id, 0]},
            }
            prompt["5"]["inputs"][f"ref_videos.ref_video_{index}"] = [components_node_id, 0]
            prompt["5"]["inputs"][f"ref_video_audios.ref_video_audio_{index}"] = [components_node_id, 1]
        for index, asset in enumerate(request.reference_audios):
            prompt[str(200 + index)] = {
                "class_type": "LoadAudio",
                "inputs": {"audio": _upload_to_comfy(resolved, asset, "audio")},
            }
            prompt["5"]["inputs"][f"ref_audios.ref_audio_{index}"] = [str(200 + index), 0]
    return prompt, seed


def _asset_cache_key(asset: VideoAsset) -> str:
    return f"index:{asset.file_index}" if asset.file_index is not None else f"id:{asset.file_id}"


def _upload_to_comfy(resolved: dict[str, _ResolvedAsset], asset: VideoAsset | None, kind: str) -> str:
    if asset is None:
        raise _ComfyUIError("영상 입력 콘텐츠가 없습니다.")
    cache_key = _asset_cache_key(asset)
    source = resolved.get(cache_key)
    if source is None or source.kind != kind:
        raise _ComfyUIError("영상 입력 콘텐츠를 준비하지 못했습니다.")
    suffix = Path(source.filename).suffix.lower() or {"image": ".png", "audio": ".wav", "video": ".mp4"}[kind]
    filename = f"local_field_{uuid.uuid4().hex}{suffix}"
    boundary = f"----LocalField{uuid.uuid4().hex}"
    fields = [("type", "input"), ("overwrite", "false")]
    body = bytearray()
    for name, value in fields:
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    field_name = "image"
    endpoint = "/upload/image"
    body.extend(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {source.media_type}\r\n\r\n".encode()
    )
    body.extend(source.content)
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = UrlRequest(
        _comfy_url(endpoint),
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 입력 파일 업로드가 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("ComfyUI 입력 파일을 업로드할 수 없습니다.") from exc
    name = result.get("name") if isinstance(result, dict) else None
    if not isinstance(name, str) or not name:
        raise _ComfyUIError("ComfyUI 입력 파일 이름을 받지 못했습니다.")
    return name


def _history_status(generation: dict[str, Any], user_id: uuid.UUID) -> VideoGenerationStatus:
    prompt_id = generation["prompt_id"]
    history = _request_json("GET", f"/history/{prompt_id}")
    entry = history.get(prompt_id)
    if not isinstance(entry, dict):
        return VideoGenerationStatus(prompt_id=prompt_id, mode=generation["mode"], status="queued")
    raw_status = entry.get("status")
    comfy_status = raw_status if isinstance(raw_status, dict) else {}
    status_name = str(comfy_status.get("status_str", ""))
    if status_name in {"error", "failed"}:
        update_video_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
        return VideoGenerationStatus(prompt_id=prompt_id, mode=generation["mode"], status="failed")
    if comfy_status.get("completed") is True:
        _sync_video_output(generation, user_id, entry.get("outputs"))
        refreshed = get_video_generation(prompt_id, user_id) or generation
        return VideoGenerationStatus(
            prompt_id=prompt_id,
            mode=generation["mode"],
            status="completed",
            video=_video_output(refreshed, user_id),
        )
    update_video_generation_status(prompt_id=prompt_id, user_id=user_id, status="processing")
    return VideoGenerationStatus(prompt_id=prompt_id, mode=generation["mode"], status="processing")


def _sync_video_output(generation: dict[str, Any], user_id: uuid.UUID, outputs: Any) -> None:
    if generation.get("storage_file_id"):
        return
    videos = _raw_video_outputs(outputs)
    video = videos[0] if videos else None
    if video is None:
        update_video_generation_status(prompt_id=generation["prompt_id"], user_id=user_id, status="failed")
        raise _ComfyUIError("ComfyUI 영상 결과를 찾을 수 없습니다.")
    filename = video.get("filename")
    if not isinstance(filename, str) or not filename:
        raise _ComfyUIError("ComfyUI 영상 파일 이름이 올바르지 않습니다.")
    subfolder = video.get("subfolder", "")
    video_type = video.get("type", "output")
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": video_type})
    content, media_type = _request_bytes(f"/view?{query}")
    file_id = storage_upload_file(content=content, media_type=media_type or "video/mp4", owner_id=str(user_id))
    update_video_generation_status(
        prompt_id=generation["prompt_id"],
        user_id=user_id,
        status="completed",
        storage_file_id=file_id,
        filename=filename,
        subfolder=subfolder,
        video_type=video_type,
    )


def _video_output(generation: dict[str, Any], user_id: uuid.UUID) -> VideoOutput | None:
    file_id = generation.get("storage_file_id")
    filename = generation.get("filename")
    if not isinstance(file_id, str) or not file_id or not isinstance(filename, str):
        return None
    return VideoOutput(
        url=storage_read_url(file_id=file_id, owner_id=str(user_id)),
        filename=filename,
        subfolder=generation.get("subfolder", ""),
        type=generation.get("video_type", "output"),
    )


def _raw_video_outputs(outputs: Any) -> list[dict[str, Any]]:
    if not isinstance(outputs, dict):
        return []
    results: list[dict[str, Any]] = []
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        values = output.get("images") or output.get("videos")
        if isinstance(values, list):
            results.extend(
                item
                for item in values
                if isinstance(item, dict) and isinstance(item.get("filename"), str)
                and Path(item["filename"]).suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
            )
    return results


def _frame_length(duration: float) -> int:
    frames = max(5, round(duration * 24))
    return frames + (5 - frames % 17) % 17


def _multiple_of_32(value: int) -> int:
    return max(32, min(1344, round(value / 32) * 32))


def _safe_filename(filename: str | None, kind: str, media_type: str | None) -> str:
    candidate = Path(filename or "").name
    if not candidate or candidate in {".", ".."}:
        candidate = f"input.{mimetypes.guess_extension(media_type or '') or {'image': '.png', 'audio': '.wav', 'video': '.mp4'}[kind]}"
    return candidate[:255]
