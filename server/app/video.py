from __future__ import annotations

import asyncio
import copy
from datetime import datetime
import json
import math
import mimetypes
import re
import secrets
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, ValidationError, field_validator
from starlette.responses import StreamingResponse

from .auth import UserResponse, current_user
from .comfyui import (
    PromptEnhancementContent,
    PromptEnhancementResponse,
    _ComfyUIError,
    _VLLMError,
    cancel_comfy_generation,
    _queue_position,
    _comfy_url,
    generation_progress,
    reset_generation_progress,
    _request_bytes,
    _request_json,
    _request_structured_object,
)
from .database import (
    advance_video_generation_segment,
    claim_video_generation_segment,
    complete_video_generation_sequence,
    create_media_asset,
    create_video_generation,
    fail_claimed_video_generation_segment,
    generation_elapsed_seconds,
    get_reusable_media,
    get_video_generation,
    update_video_generation_status,
)
from .generation_events import generation_event_broker, generation_key
from .media_editing import MediaEditError, concat_video_segments, extract_last_video_frame
from .storage import (
    StorageError,
    delete_file as storage_delete_file,
    download_file as storage_download_file,
    enabled as storage_enabled,
    read_url as storage_read_url,
    upload_file as storage_upload_file,
)
from .prompts import VIDEO_PROMPT_ENHANCEMENT_SYSTEM_PROMPT, VIDEO_PROMPT_ENHANCEMENT_USER_PROMPT


router = APIRouter(prefix="/generation/video", tags=["video generation"])
_WORKFLOW_DIR = Path(__file__).with_name("workflows")
_ALLOWED_MODES = {"i2v", "fl2v", "r2v"}
_MAX_SEED = 2**63 - 1
_MAX_INPUT_SIZE = 50 * 1024 * 1024
_SEGMENT_SECONDS = 10.0
_FILE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_VIDEO_PROMPT_COMMON_CHARS = r"\x20-\x2F\x30-\x39\x3A-\x40\x5B-\x60\x7B-\x7E\n"
_VIDEO_PROMPT_LANGUAGE_CHARS = {
    "ko": r"\u1100-\u11FF\u3131-\u318E\uAC00-\uD7A3",
    "en": r"A-Za-z",
    "ja": r"\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uFF66-\uFF9D",
}
_VIDEO_PROMPT_LANGUAGE_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese"}
_VIDEO_PROMPT_FIELDS = ("style", "timeline", "camera", "audio", "text", "negative")
_VIDEO_PROMPT_SECTION_LABELS = {
    "ko": ("스타일:", "타임라인:", "카메라:", "오디오:", "텍스트:", "부정:"),
    "en": ("Style:", "Timeline:", "Camera:", "Audio:", "Text:", "Negative:"),
    "ja": ("スタイル:", "タイムライン:", "カメラ:", "オーディオ:", "テキスト:", "ネガティブ:"),
}


class VideoAsset(BaseModel):
    kind: Literal["image", "audio", "video"]
    file_id: str | None = Field(default=None, max_length=64)
    file_index: int | None = Field(default=None, ge=0, le=20)


class VideoGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    prompt_enhancement_enabled: bool = False
    improved_prompt: str | None = Field(default=None, max_length=5000)
    segment_prompts: list[str] = Field(default_factory=list, max_length=360)
    improved_segment_prompts: list[str] = Field(default_factory=list, max_length=360)
    prompt_output_languages: list[Literal["ko", "en", "ja"]] = Field(default_factory=lambda: ["en"], min_length=1, max_length=3)
    width: int = Field(default=1344, ge=32, le=1344)
    height: int = Field(default=768, ge=32, le=1344)
    duration: float = Field(default=5)
    fps: float = Field(default=24, ge=1, le=120)
    seed: int | None = Field(default=None, ge=0, le=_MAX_SEED)
    first_frame: VideoAsset | None = None
    last_frame: VideoAsset | None = None
    reference_images: list[VideoAsset] = Field(default_factory=list, max_length=9)
    reference_videos: list[VideoAsset] = Field(default_factory=list, max_length=3)
    reference_audios: list[VideoAsset] = Field(default_factory=list, max_length=3)

    @field_validator("prompt_output_languages")
    @classmethod
    def unique_prompt_output_languages(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("동영상 프롬프트 출력 언어는 중복 선택할 수 없습니다.")
        return value


class VideoPromptEnhancementRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    mode: Literal["i2v", "fl2v", "r2v"]
    duration: float = Field(default=5)
    segment_index: int = Field(default=0, ge=0, le=359)
    segment_count: int = Field(default=1, ge=1, le=360)
    previous_segment_prompt: str | None = Field(default=None, max_length=5000)
    prompt_output_languages: list[Literal["ko", "en", "ja"]] = Field(default_factory=lambda: ["en"], min_length=1, max_length=3)

    @field_validator("prompt_output_languages")
    @classmethod
    def unique_prompt_output_languages(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("동영상 프롬프트 출력 언어는 중복 선택할 수 없습니다.")
        return value


class VideoGenerationAccepted(BaseModel):
    prompt_id: str
    client_id: str
    generation_id: str
    mode: str
    status: Literal["queued"]
    progress: float = Field(default=0, ge=0, le=100)
    fps: float = Field(default=24, ge=1, le=120)
    segment_count: int = Field(default=1, ge=1)
    created_at: datetime
    elapsed_seconds: float = Field(default=0, ge=0)


class VideoOutput(BaseModel):
    url: str
    filename: str
    subfolder: str
    type: str


class VideoGenerationStatus(BaseModel):
    prompt_id: str
    mode: str
    status: str
    progress: float = Field(default=0, ge=0, le=100)
    queue_position: int | None = Field(default=None, ge=1)
    fps: float = Field(default=24, ge=1, le=120)
    segment_index: int = Field(default=0, ge=0)
    segment_count: int = Field(default=1, ge=1)
    created_at: datetime | None = None
    elapsed_seconds: float = Field(default=0, ge=0)
    video: VideoOutput | None = None


_REFERENCE_MARKER_REPLACEMENTS = (
    (re.compile(r"\[\s*(?:image|picture)\s*(\d+)\s*\]", re.IGNORECASE), r"<Picture \1>"),
    (re.compile(r"@\s*image\s*(\d+)", re.IGNORECASE), r"<Picture \1>"),
    (re.compile(r"\[\s*video\s*(\d+)\s*\]", re.IGNORECASE), r"<Video \1>"),
    (re.compile(r"@\s*video\s*(\d+)", re.IGNORECASE), r"<Video \1>"),
    (re.compile(r"\[\s*audio\s*(\d+)\s*\]", re.IGNORECASE), r"<Audio \1>"),
    (re.compile(r"@\s*audio\s*(\d+)", re.IGNORECASE), r"<Audio \1>"),
)


class _ResolvedAsset:
    def __init__(self, *, file_id: str, filename: str, content: bytes, media_type: str, kind: str):
        self.file_id = file_id
        self.filename = filename
        self.content = content
        self.media_type = media_type
        self.kind = kind


@router.post("/enhance-prompt", response_model=PromptEnhancementResponse)
def enhance_video_prompt(
    payload: VideoPromptEnhancementRequest,
    _: UserResponse = Depends(current_user),
) -> PromptEnhancementResponse:
    try:
        return _enhance_video_prompt(payload)
    except _VLLMError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


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
        segment_durations = _video_segment_durations(request.duration)
        effective_prompts = _effective_video_prompts(mode, request)
        resolved = await _resolve_assets(mode, request, files, user)
        initial_request = request.model_copy(update={"duration": segment_durations[0]})
        prompt, seed = _build_prompt(mode, initial_request, resolved, effective_prompt=effective_prompts[0])
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
    generation_id, created_at = create_video_generation(
        user_id=user.id,
        prompt_id=prompt_id,
        client_id=client_id,
        active_prompt_id=prompt_id,
        mode=mode,
        prompt=effective_prompts[0],
        width=request.width,
        height=request.height,
        length=_frame_length(request.duration, request.fps),
        fps=request.fps,
        seed=seed,
        input_file_ids=input_file_ids,
        segment_prompts=effective_prompts,
        segment_durations=segment_durations,
    )
    return VideoGenerationAccepted(
        prompt_id=prompt_id,
        client_id=client_id,
        generation_id=str(generation_id),
        mode=mode,
        status="queued",
        progress=0,
        fps=request.fps,
        segment_count=len(segment_durations),
        created_at=created_at,
        elapsed_seconds=0,
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


@router.post("/{mode}/{prompt_id}/cancel", response_model=VideoGenerationStatus)
def cancel_video_generation(
    mode: Literal["i2v", "fl2v", "r2v"],
    prompt_id: str,
    user: UserResponse = Depends(current_user),
) -> VideoGenerationStatus:
    generation = get_video_generation(prompt_id, user.id)
    if generation is None or generation["mode"] != mode:
        raise HTTPException(status_code=404, detail="영상 생성 결과를 찾을 수 없습니다.")
    if generation["status"] == "cancelled":
        return _cancelled_status(generation, user.id)
    if generation["status"] not in {"queued", "processing"}:
        return _history_status(generation, user.id)
    active_prompt_id = generation.get("active_prompt_id", prompt_id)
    try:
        if isinstance(active_prompt_id, str) and active_prompt_id:
            dispatched = cancel_comfy_generation(active_prompt_id)
            if not dispatched:
                current = _history_status(generation, user.id)
                if current.status in {"completed", "failed", "cancelled"}:
                    return current
                raise HTTPException(status_code=409, detail="이미 처리 중인 작업이라 취소할 수 없습니다.")
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    update_video_generation_status(prompt_id=prompt_id, user_id=user.id, status="cancelled")
    _delete_internal_sequence_files(generation.get("segment_file_ids", []), user.id)
    cancelled = get_video_generation(prompt_id, user.id) or generation
    _, progress = _video_sequence_progress(cancelled, user.id)
    data = {
        "prompt_id": prompt_id,
        "mode": mode,
        "status": "cancelled",
        "progress": progress,
        "queue_position": None,
        **_video_timing(cancelled, user.id),
    }
    generation_event_broker.publish(
        key=generation_key("video", user.id, prompt_id),
        event="cancelled",
        data=data,
    )
    return VideoGenerationStatus(**data)


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
    key = generation_key("video", user_id, prompt_id)
    async with generation_event_broker.subscribe(key) as events:
        generation = await asyncio.to_thread(get_video_generation, prompt_id, user_id)
        if generation is None or generation["mode"] != mode:
            yield _sse_message("failed", {"prompt_id": prompt_id, "status": "failed", "message": "영상 생성 결과를 찾을 수 없습니다."})
            return

        current_status = str(generation["status"])
        if current_status == "completed":
            try:
                video = await asyncio.to_thread(_video_output, generation, user_id)
            except StorageError as exc:
                yield _sse_message("error", {"prompt_id": prompt_id, "message": str(exc)})
                return
            yield _sse_message(
                "completed",
                VideoGenerationStatus(
                    prompt_id=prompt_id,
                    mode=mode,
                    status="completed",
                    video=video,
                    **_video_timing(generation, user_id),
                ).model_dump(mode="json"),
            )
            return
        if current_status == "failed":
            yield _sse_message(
                "failed",
                {
                    "prompt_id": prompt_id,
                    "mode": mode,
                    "status": "failed",
                    "progress": 0,
                    "queue_position": None,
                    **_video_timing(generation, user_id),
                },
            )
            return
        if current_status == "cancelled":
            yield _sse_message("cancelled", _cancelled_status(generation, user_id).model_dump(mode="json"))
            return
        progress_state, progress = _video_sequence_progress(generation, user_id)
        active_prompt_id = generation.get("active_prompt_id", prompt_id)
        yield _sse_message(
            "status",
            {
                "prompt_id": prompt_id,
                "mode": mode,
                "status": current_status,
                "progress": progress,
                "queue_position": progress_state["queue_position"] or _queue_position(active_prompt_id)
                if isinstance(active_prompt_id, str)
                else None,
                **_video_timing(generation, user_id),
            },
        )

        while True:
            try:
                message = await asyncio.wait_for(events.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield _sse_message(message["event"], message["data"])
            if message["event"] in {"completed", "failed", "cancelled", "error"}:
                return


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
        raise HTTPException(status_code=422, detail="R2V는 참조 콘텐츠를 사용합니다.")
    if any(asset.kind != "image" for asset in request.reference_images):
        raise HTTPException(status_code=422, detail="R2V 참조 이미지 구성이 올바르지 않습니다.")
    if any(asset.kind != "video" for asset in request.reference_videos):
        raise HTTPException(status_code=422, detail="R2V 참조 동영상 구성이 올바르지 않습니다.")
    if any(asset.kind != "audio" for asset in request.reference_audios):
        raise HTTPException(status_code=422, detail="R2V 참조 오디오 구성이 올바르지 않습니다.")
    if not request.reference_images and not request.reference_videos and not request.reference_audios:
        raise HTTPException(status_code=422, detail="R2V에는 참조 이미지·동영상 또는 오디오가 필요합니다.")
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


def _video_prompt_pattern(languages: Sequence[str]) -> str:
    if not languages or any(language not in _VIDEO_PROMPT_LANGUAGE_CHARS for language in languages):
        raise ValueError("지원하지 않는 동영상 프롬프트 출력 언어입니다.")
    language_chars = "".join(_VIDEO_PROMPT_LANGUAGE_CHARS[language] for language in dict.fromkeys(languages))
    return rf"^(?:[{_VIDEO_PROMPT_COMMON_CHARS}{language_chars}]|image|video|audio)+$"


def _video_prompt_section_labels(languages: Sequence[str]) -> tuple[str, ...]:
    if not languages or languages[0] not in _VIDEO_PROMPT_SECTION_LABELS:
        raise ValueError("동영상 프롬프트 출력 언어가 없습니다.")
    return _VIDEO_PROMPT_SECTION_LABELS[languages[0]]


def _validate_video_prompt_contents(contents: str, languages: Sequence[str]) -> str:
    contents = _normalize_video_reference_markers(contents.strip())
    if not re.fullmatch(_video_prompt_pattern(languages), contents):
        raise _VLLMError("동영상 프롬프트에 선택하지 않은 언어 또는 허용되지 않은 문자가 포함되어 있습니다.")
    labels = _video_prompt_section_labels(languages)
    positions: list[int] = []
    for label in labels:
        match = re.search(rf"(?m)^{re.escape(label)}[ ]*$", contents)
        if match is None:
            raise _VLLMError("동영상 프롬프트의 Atlas 6블록 형식이 올바르지 않습니다.")
        positions.append(match.start())
    if positions != sorted(positions):
        raise _VLLMError("동영상 프롬프트의 Atlas 6블록 순서가 올바르지 않습니다.")
    for index, position in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else len(contents)
        if not contents[position:end].split("\n", 1)[-1].strip():
            raise _VLLMError("동영상 프롬프트의 Atlas 6블록 내용이 비어 있습니다.")
    return contents


def _enhance_video_prompt(payload: VideoPromptEnhancementRequest) -> PromptEnhancementResponse:
    languages = payload.prompt_output_languages
    pattern = _video_prompt_pattern(languages)
    fields = _request_structured_object(
        system_prompt=VIDEO_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
        user_prompt=VIDEO_PROMPT_ENHANCEMENT_USER_PROMPT.format(
            prompt=payload.prompt.strip(),
            mode=payload.mode,
            duration=f"{payload.duration:g}",
            segment_number=payload.segment_index + 1,
            segment_count=payload.segment_count,
            previous_segment_prompt=(payload.previous_segment_prompt or "none").strip() or "none",
            languages=", ".join(_VIDEO_PROMPT_LANGUAGE_NAMES[language] for language in languages),
        ),
        max_tokens=1536,
        temperature=0.8,
        schema=_video_prompt_fields_schema(pattern),
        name="video_prompt_fields",
    )
    fields = _validate_video_prompt_fields(fields, pattern)
    contents = _assemble_video_prompt(fields, languages)
    return PromptEnhancementResponse(improved_prompt=PromptEnhancementContent(contents=contents))


def _video_prompt_fields_schema(pattern: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            field: {"type": "string", "minLength": 1, "maxLength": 1000, "pattern": pattern}
            for field in _VIDEO_PROMPT_FIELDS
        },
        "required": list(_VIDEO_PROMPT_FIELDS),
        "additionalProperties": False,
    }


def _validate_video_prompt_fields(fields: dict[str, Any], pattern: str) -> dict[str, str]:
    if set(fields) != set(_VIDEO_PROMPT_FIELDS):
        raise _VLLMError("vLLM 동영상 프롬프트 JSON 필드가 올바르지 않습니다.")
    validated: dict[str, str] = {}
    for field in _VIDEO_PROMPT_FIELDS:
        value = fields[field]
        value = _normalize_video_reference_markers(value.strip()) if isinstance(value, str) else value
        if not isinstance(value, str) or not value or not re.fullmatch(pattern, value):
            raise _VLLMError("vLLM 동영상 프롬프트 JSON 필드에 허용되지 않은 값이 있습니다.")
        validated[field] = value.strip()
    return validated


def _normalize_video_reference_markers(contents: str) -> str:
    for pattern, replacement in _REFERENCE_MARKER_REPLACEMENTS:
        contents = pattern.sub(replacement, contents)
    return contents


def _assemble_video_prompt(fields: dict[str, str], languages: Sequence[str]) -> str:
    labels = _video_prompt_section_labels(languages)
    contents = "\n".join(
        f"{label}\n{fields[field]}" for label, field in zip(labels, _VIDEO_PROMPT_FIELDS, strict=True)
    )
    if len(contents) > 5000:
        raise _VLLMError("조립된 동영상 프롬프트가 길이 제한을 초과했습니다.")
    return contents


def _video_reference_prompt(mode: str, request: VideoGenerationRequest) -> str:
    language = request.prompt_output_languages[0]
    if language == "ko":
        heading = "참조:"
        descriptions = {
            "i2v_first": "시작 이미지 참조. 주체와 구도를 유지합니다.",
            "fl2v_first": "첫 프레임 참조. 시작 구도를 유지합니다.",
            "fl2v_last": "마지막 프레임 참조. 종료 구도를 유지합니다.",
            "image": "이미지 참조. 주체와 시각적 정체성을 유지합니다.",
            "video": "동영상 참조. 움직임의 리듬과 카메라 동작을 참고합니다.",
            "audio": "오디오 참조. 분위기와 타이밍을 참고합니다.",
        }
    elif language == "ja":
        heading = "参照:"
        descriptions = {
            "i2v_first": "開始画像の参照。被写体と構図を維持します。",
            "fl2v_first": "最初のフレームの参照。開始構図を維持します。",
            "fl2v_last": "最後のフレームの参照。終了構図を維持します。",
            "image": "画像の参照。被写体と視覚的な一貫性を維持します。",
            "video": "動画の参照。動きのリズムとカメラ動作を参考にします。",
            "audio": "音声の参照。雰囲気とタイミングを参考にします。",
        }
    else:
        heading = "Reference:"
        descriptions = {
            "i2v_first": "start-image reference. Preserve the subject and composition.",
            "fl2v_first": "first-frame reference. Preserve the opening composition.",
            "fl2v_last": "last-frame reference. Preserve the closing composition.",
            "image": "image reference. Preserve the subject and visual identity.",
            "video": "video reference. Follow its motion rhythm and camera movement.",
            "audio": "audio reference. Follow its mood and timing.",
        }
    lines = [heading]
    if mode == "i2v":
        lines.append(f"<Picture 1>: {descriptions['i2v_first']}")
    elif mode == "fl2v":
        lines.extend(
            [
                f"<Picture 1>: {descriptions['fl2v_first']}",
                f"<Picture 2>: {descriptions['fl2v_last']}",
            ]
        )
    else:
        lines.extend(
            [
                *(f"<Picture {index}>: {descriptions['image']}" for index, _ in enumerate(request.reference_images, start=1)),
                *(f"<Video {index}>: {descriptions['video']}" for index, _ in enumerate(request.reference_videos, start=1)),
                *(f"<Audio {index}>: {descriptions['audio']}" for index, _ in enumerate(request.reference_audios, start=1)),
            ]
        )
    return "\n".join(lines)


def _video_segment_durations(duration: float) -> list[float]:
    if not math.isfinite(duration) or duration <= 0:
        raise HTTPException(status_code=422, detail="영상 길이는 0초보다 커야 합니다.")
    segments: list[float] = []
    remaining = duration
    while remaining > 1e-6:
        segment = min(_SEGMENT_SECONDS, remaining)
        segments.append(round(segment, 3))
        remaining = round(remaining - segment, 6)
    if len(segments) > 360:
        raise HTTPException(status_code=422, detail="영상은 최대 360개 구간까지 생성할 수 있습니다.")
    return segments


def _segment_prompt_values(
    values: list[str], legacy_value: str | None, segment_count: int, label: str
) -> list[str]:
    source = values or ([legacy_value] if segment_count == 1 and legacy_value is not None else [])
    if len(source) != segment_count:
        raise HTTPException(status_code=422, detail=f"{label} 수가 10초 구간 수와 일치해야 합니다.")
    result = [value.strip() if isinstance(value, str) else "" for value in source]
    if any(not value or len(value) > 5000 for value in result):
        raise HTTPException(status_code=422, detail=f"{label}은 구간마다 1~5000자여야 합니다.")
    return result


def _continuation_reference_prompt(request: VideoGenerationRequest) -> str:
    language = request.prompt_output_languages[0]
    if language == "ko":
        return "참조:\n<Picture 1>: 직전 영상 구간의 실제 마지막 프레임 참조. 주체, 구도, 조명과 시각적 연속성을 유지합니다."
    if language == "ja":
        return "参照:\n<Picture 1>: 直前の動画区間の実際の最終フレームを参照。被写体、構図、照明、視覚的一貫性を維持します。"
    return "Reference:\n<Picture 1>: actual final-frame reference from the previous video segment. Preserve subject, composition, lighting, and visual continuity."


def _effective_video_prompts(mode: str, request: VideoGenerationRequest) -> list[str]:
    segment_count = len(_video_segment_durations(request.duration))
    raw_prompts = _segment_prompt_values(request.segment_prompts, request.prompt, segment_count, "프롬프트")
    if not request.prompt_enhancement_enabled:
        return raw_prompts
    improved_prompts = _segment_prompt_values(
        request.improved_segment_prompts, request.improved_prompt, segment_count, "개선된 프롬프트"
    )
    result: list[str] = []
    for index, improved_prompt in enumerate(improved_prompts):
        try:
            improved_prompt = _validate_video_prompt_contents(improved_prompt, request.prompt_output_languages)
        except _VLLMError as exc:
            raise HTTPException(status_code=422, detail="개선된 동영상 프롬프트 형식이 올바르지 않습니다.") from exc
        reference_prompt = _video_reference_prompt(mode, request) if index == 0 else _continuation_reference_prompt(request)
        result.append(f"{reference_prompt}\n\n{improved_prompt}")
    return result


def _effective_video_prompt(mode: str, request: VideoGenerationRequest) -> str:
    return _effective_video_prompts(mode, request)[0]


def _build_prompt(
    mode: str,
    request: VideoGenerationRequest,
    resolved: dict[str, _ResolvedAsset],
    *,
    effective_prompt: str | None = None,
) -> tuple[dict[str, dict[str, Any]], int]:
    try:
        with (_WORKFLOW_DIR / f"video_{mode}.json").open(encoding="utf-8") as handle:
            prompt = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise _ComfyUIError(f"{mode} 영상 workflow를 읽을 수 없습니다.") from exc
    prompt = copy.deepcopy(prompt)
    seed = request.seed if request.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    effective_prompt = effective_prompt if effective_prompt is not None else _effective_video_prompt(mode, request)
    for node in prompt.values():
        if isinstance(node, dict) and isinstance(node.get("inputs"), dict):
            inputs = node["inputs"]
            if "prompt" in inputs and node.get("class_type") in {"MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"}:
                inputs["prompt"] = effective_prompt
            if node.get("class_type") == "RandomNoise":
                inputs["noise_seed"] = seed
            if node.get("class_type") in {"MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"}:
                inputs["width"] = _multiple_of_32(request.width)
                inputs["height"] = _multiple_of_32(request.height)
                inputs["length"] = _frame_length(request.duration, request.fps)
            if node.get("class_type") == "CreateVideo":
                inputs["fps"] = request.fps
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


def _generation_segment_durations(generation: dict[str, Any]) -> list[float]:
    values = generation.get("segment_durations")
    if isinstance(values, list) and values and all(isinstance(value, (int, float)) and value > 0 for value in values):
        return [float(value) for value in values]
    return [max(float(generation.get("length") or 1) / float(generation.get("fps") or 24), 1 / 24)]


def _generation_segment_prompts(generation: dict[str, Any]) -> list[str]:
    values = generation.get("segment_prompts")
    if isinstance(values, list) and values and all(isinstance(value, str) and value for value in values):
        return values
    return [str(generation.get("prompt") or "")]


def _video_sequence_fields(generation: dict[str, Any]) -> dict[str, int]:
    count = len(_generation_segment_durations(generation))
    raw_index = generation.get("segment_index", 0)
    index = int(raw_index) if isinstance(raw_index, int) else 0
    return {"segment_index": min(max(index, 0), count - 1), "segment_count": count}


def _video_sequence_progress(generation: dict[str, Any], user_id: uuid.UUID) -> tuple[dict[str, Any], float]:
    progress_state = generation_progress(generation["prompt_id"], user_id)
    fields = _video_sequence_fields(generation)
    if generation.get("status") == "completed":
        return progress_state, 100.0
    progress = (fields["segment_index"] + progress_state["progress"] / 100) / fields["segment_count"] * 100
    return progress_state, round(max(0.0, min(100.0, progress)), 3)


def _video_timing(generation: dict[str, Any], user_id: uuid.UUID) -> dict[str, Any]:
    current = get_video_generation(generation["prompt_id"], user_id) or generation
    created_at = current.get("created_at")
    return {
        "fps": float(current.get("fps") or 24),
        **_video_sequence_fields(current),
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "elapsed_seconds": generation_elapsed_seconds(current),
    }


def _delete_internal_sequence_files(file_ids: Sequence[object], user_id: uuid.UUID) -> None:
    for file_id in dict.fromkeys(file_ids):
        if not isinstance(file_id, str) or not file_id:
            continue
        try:
            storage_delete_file(file_id=file_id, owner_id=str(user_id))
        except StorageError:
            continue


def _cancelled_status(generation: dict[str, Any], user_id: uuid.UUID) -> VideoGenerationStatus:
    _, progress = _video_sequence_progress(generation, user_id)
    return VideoGenerationStatus(
        prompt_id=generation["prompt_id"],
        mode=generation["mode"],
        status="cancelled",
        progress=progress,
        queue_position=None,
        **_video_timing(generation, user_id),
    )


def _history_status(generation: dict[str, Any], user_id: uuid.UUID) -> VideoGenerationStatus:
    prompt_id = generation["prompt_id"]
    if generation.get("status") == "completed":
        return VideoGenerationStatus(
            prompt_id=prompt_id,
            mode=generation["mode"],
            status="completed",
            progress=100,
            queue_position=None,
            video=_video_output(generation, user_id),
            **_video_timing(generation, user_id),
        )
    if generation.get("status") == "failed":
        _, progress = _video_sequence_progress(generation, user_id)
        return VideoGenerationStatus(
            prompt_id=prompt_id,
            mode=generation["mode"],
            status="failed",
            progress=progress,
            queue_position=None,
            **_video_timing(generation, user_id),
        )
    if generation.get("status") == "cancelled":
        return _cancelled_status(generation, user_id)
    active_prompt_id = generation.get("active_prompt_id", prompt_id)
    progress_state, progress = _video_sequence_progress(generation, user_id)
    if not isinstance(active_prompt_id, str) or not active_prompt_id:
        return VideoGenerationStatus(
            prompt_id=prompt_id,
            mode=generation["mode"],
            status="processing",
            progress=progress,
            queue_position=None,
            **_video_timing(generation, user_id),
        )
    history = _request_json("GET", f"/history/{active_prompt_id}")
    entry = history.get(active_prompt_id)
    if not isinstance(entry, dict):
        current_status = progress_state["status"] or "queued"
        if current_status == "processing":
            update_video_generation_status(prompt_id=prompt_id, user_id=user_id, status="processing")
        elif current_status == "failed":
            update_video_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
            _delete_internal_sequence_files(generation.get("segment_file_ids", []), user_id)
        return VideoGenerationStatus(
            prompt_id=prompt_id,
            mode=generation["mode"],
            status=current_status,
            progress=progress,
            queue_position=progress_state["queue_position"] or _queue_position(active_prompt_id),
            **_video_timing(generation, user_id),
        )
    raw_status = entry.get("status")
    comfy_status = raw_status if isinstance(raw_status, dict) else {}
    status_name = str(comfy_status.get("status_str", ""))
    if status_name in {"error", "failed"}:
        update_video_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
        _delete_internal_sequence_files(generation.get("segment_file_ids", []), user_id)
        return VideoGenerationStatus(
            prompt_id=prompt_id,
            mode=generation["mode"],
            status="failed",
            progress=progress,
            **_video_timing(generation, user_id),
        )
    if comfy_status.get("completed") is True:
        _sync_video_output(generation, user_id, active_prompt_id, entry.get("outputs"))
        refreshed = get_video_generation(prompt_id, user_id) or generation
        if refreshed.get("status") == "completed":
            return VideoGenerationStatus(
                prompt_id=prompt_id,
                mode=generation["mode"],
                status="completed",
                progress=100,
                video=_video_output(refreshed, user_id),
                **_video_timing(refreshed, user_id),
            )
        if refreshed.get("status") == "cancelled":
            return _cancelled_status(refreshed, user_id)
        refreshed_progress_state, refreshed_progress = _video_sequence_progress(refreshed, user_id)
        next_prompt_id = refreshed.get("active_prompt_id")
        return VideoGenerationStatus(
            prompt_id=prompt_id,
            mode=generation["mode"],
            status=str(refreshed.get("status") or "processing"),
            progress=refreshed_progress,
            queue_position=refreshed_progress_state["queue_position"] or _queue_position(next_prompt_id) if isinstance(next_prompt_id, str) else None,
            **_video_timing(refreshed, user_id),
        )
    update_video_generation_status(prompt_id=prompt_id, user_id=user_id, status="processing")
    return VideoGenerationStatus(
        prompt_id=prompt_id,
        mode=generation["mode"],
        status="processing",
        progress=progress,
        **_video_timing(generation, user_id),
    )


def _queue_r2v_continuation(
    generation: dict[str, Any],
    user_id: uuid.UUID,
    frame_file_id: str,
    frame_content: bytes,
) -> str:
    fields = _video_sequence_fields(generation)
    next_index = fields["segment_index"] + 1
    durations = _generation_segment_durations(generation)
    prompts = _generation_segment_prompts(generation)
    if next_index >= len(durations) or next_index >= len(prompts):
        raise _ComfyUIError("다음 영상 구간 정보를 찾을 수 없습니다.")
    continuation = VideoAsset(kind="image", file_id=frame_file_id)
    request = VideoGenerationRequest(
        prompt=prompts[next_index],
        width=int(generation["width"]),
        height=int(generation["height"]),
        duration=durations[next_index],
        fps=float(generation["fps"]),
        seed=int(generation["seed"]),
        reference_images=[continuation],
    )
    # ponytail: follow-on R2V uses only the generated final frame; persist original auxiliary references only if needed.
    resolved = {
        _asset_cache_key(continuation): _ResolvedAsset(
            file_id=frame_file_id,
            filename=f"{generation['prompt_id']}-segment-{next_index:03d}-last-frame.png",
            content=frame_content,
            media_type="image/png",
            kind="image",
        )
    }
    prompt, _ = _build_prompt("r2v", request, resolved, effective_prompt=prompts[next_index])
    response = _request_json("POST", "/prompt", {"prompt": prompt, "client_id": generation["client_id"]})
    next_prompt_id = response.get("prompt_id")
    if not isinstance(next_prompt_id, str) or not next_prompt_id:
        raise _ComfyUIError("ComfyUI가 다음 R2V 작업 ID를 반환하지 않았습니다.")
    return next_prompt_id


def _sync_video_output(
    generation: dict[str, Any], user_id: uuid.UUID, active_prompt_id: str, outputs: Any
) -> None:
    claimed = claim_video_generation_segment(
        prompt_id=generation["prompt_id"], user_id=user_id, active_prompt_id=active_prompt_id
    )
    if claimed is None:
        return
    videos = _raw_video_outputs(outputs)
    video = videos[0] if videos else None
    if video is None:
        fail_claimed_video_generation_segment(prompt_id=claimed["prompt_id"], user_id=user_id)
        raise _ComfyUIError("ComfyUI 영상 결과를 찾을 수 없습니다.")
    filename = video.get("filename")
    subfolder = video.get("subfolder", "")
    video_type = video.get("type", "output")
    if not isinstance(filename, str) or not filename or not isinstance(subfolder, str) or not isinstance(video_type, str):
        fail_claimed_video_generation_segment(prompt_id=claimed["prompt_id"], user_id=user_id)
        raise _ComfyUIError("ComfyUI 영상 파일 정보가 올바르지 않습니다.")
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": video_type})
    segment_file_id: str | None = None
    frame_file_id: str | None = None
    next_prompt_id: str | None = None
    advanced = False
    try:
        content, media_type = _request_bytes(f"/view?{query}")
        fields = _video_sequence_fields(claimed)
        if fields["segment_index"] + 1 >= fields["segment_count"]:
            segments: list[tuple[bytes, str]] = []
            for index, file_id in enumerate(claimed.get("segment_file_ids", [])):
                prior_content, _ = storage_download_file(file_id=file_id, owner_id=str(user_id))
                segments.append((prior_content, f"segment-{index:03d}.mp4"))
            final_content = content
            final_filename = filename
            final_media_type = media_type or "video/mp4"
            if segments:
                merged = concat_video_segments(segments=[*segments, (content, filename)])
                final_content = merged.content
                final_filename = f"{Path(filename).stem}-sequence.mp4"
                final_media_type = "video/mp4"
                subfolder = ""
                video_type = "output"
            final_file_id = storage_upload_file(
                content=final_content, media_type=final_media_type, owner_id=str(user_id)
            )
            completed = complete_video_generation_sequence(
                prompt_id=claimed["prompt_id"], user_id=user_id, segment_index=fields["segment_index"],
                storage_file_id=final_file_id, filename=final_filename, subfolder=subfolder,
                video_type=video_type, size_bytes=len(final_content),
            )
            if not completed:
                _delete_internal_sequence_files([final_file_id], user_id)
                return
            _delete_internal_sequence_files(claimed.get("segment_file_ids", []), user_id)
            return

        segment_file_id = storage_upload_file(
            content=content, media_type=media_type or "video/mp4", owner_id=str(user_id)
        )
        frame_content = extract_last_video_frame(content=content, filename=filename)
        frame_file_id = storage_upload_file(content=frame_content, media_type="image/png", owner_id=str(user_id))
        next_prompt_id = _queue_r2v_continuation(claimed, user_id, frame_file_id, frame_content)
        advanced = advance_video_generation_segment(
            prompt_id=claimed["prompt_id"], user_id=user_id, segment_index=fields["segment_index"],
            next_prompt_id=next_prompt_id, segment_file_id=segment_file_id,
        )
        if not advanced:
            cancel_comfy_generation(next_prompt_id)
            return
        reset_generation_progress(claimed["prompt_id"], user_id)
    except (StorageError, MediaEditError, _ComfyUIError):
        fail_claimed_video_generation_segment(prompt_id=claimed["prompt_id"], user_id=user_id)
        if next_prompt_id:
            try:
                cancel_comfy_generation(next_prompt_id)
            except _ComfyUIError:
                pass
        raise
    finally:
        if frame_file_id:
            _delete_internal_sequence_files([frame_file_id], user_id)
        if segment_file_id and not advanced:
            _delete_internal_sequence_files([segment_file_id], user_id)


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


def _frame_length(duration: float, fps: float = 24) -> int:
    frames = max(5, round(duration * fps))
    return frames + (5 - frames % 17) % 17


def _multiple_of_32(value: int) -> int:
    return max(32, min(1344, round(value / 32) * 32))


def _safe_filename(filename: str | None, kind: str, media_type: str | None) -> str:
    candidate = Path(filename or "").name
    if not candidate or candidate in {".", ".."}:
        candidate = f"input.{mimetypes.guess_extension(media_type or '') or {'image': '.png', 'audio': '.wav', 'video': '.mp4'}[kind]}"
    return candidate[:255]
