from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime
import json
from pathlib import Path
import secrets
from typing import Any, Literal
from urllib.parse import urlencode
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.responses import StreamingResponse

from .auth import UserResponse, current_user
from .comfyui import (
    _ComfyUIError,
    _VLLMError,
    _queue_position,
    _request_bytes,
    _request_json,
    _request_structured_object,
    cancel_comfy_generation,
    generation_progress,
)
from .database import (
    create_music_generation,
    generation_elapsed_seconds,
    get_latest_music_generation,
    get_music_generation,
    update_music_generation_status,
)
from .generation_events import generation_event_broker, generation_key
from .prompts import (
    MUSIC_DESCRIPTION_ENHANCEMENT_SYSTEM_PROMPT,
    MUSIC_LYRICS_ENHANCEMENT_SYSTEM_PROMPT,
    MUSIC_PROMPT_ENHANCEMENT_USER_PROMPT,
)
from .storage import StorageError, enabled as storage_enabled, read_url as storage_read_url, upload_file as storage_upload_file


router = APIRouter(prefix="/generation/music", tags=["music generation"])
_WORKFLOW_PATH = Path(__file__).with_name("workflows") / "music_t2m.json"
_MAX_SEED = 2**53 - 1
_MUSIC_PROMPT_COMMON_CHARS = r"\x20-\x2F\x30-\x39\x3A-\x40\x5B-\x60\x7B-\x7E\n"
_MUSIC_PROMPT_NON_WHITESPACE_COMMON_CHARS = r"\x21-\x2F\x30-\x39\x3A-\x40\x5B-\x60\x7B-\x7E"
_MUSIC_PROMPT_LANGUAGE_CHARS = {
    "ko": r"\u1100-\u11FF\u3131-\u318E\uAC00-\uD7A3",
    "en": r"A-Za-z",
    "ja": r"\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uFF66-\uFF9D",
}
_MUSIC_PROMPT_NON_WHITESPACE_LANGUAGE_CHARS = {
    **_MUSIC_PROMPT_LANGUAGE_CHARS,
    "ja": r"\u3001-\u303F\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uFF66-\uFF9D",
}
_MUSIC_PROMPT_LANGUAGE_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese"}
_MUSIC_PROMPT_FIXED_TOKENS = "Verse|Pre-Chorus|Chorus|Bridge|Intro|Outro|Instrumental|Hook|Rap"
_MUSIC_PROMPT_MAX_TOKENS = 4096
_MUSIC_PROMPT_TIMEOUT_SECONDS = 300
_MODEL_FILES = {
    ("UNETLoader", "unet_name"): "minimax_music3_dit_fp16.safetensors",
    ("CLIPLoader", "clip_name"): "minimax_music3_text_encoder_pruned_int8_convrot.safetensors",
    ("VAELoader", "vae_name"): "minimax_music3_dav.safetensors",
}
_AUDIO_TYPES = {
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
}


class MusicGenerationOptions(BaseModel):
    model: Literal["MiniMax-Music3"]
    service_available: bool
    detail: str
    default_duration_seconds: int = 60
    max_duration_seconds: int = 300


class MusicGenerationRequest(BaseModel):
    description: str = Field(min_length=1, max_length=5000)
    lyrics: str = Field(default="", max_length=5000)
    duration_seconds: float = Field(default=60, ge=10, le=300)
    seed: int | None = Field(default=None, ge=0, le=_MAX_SEED)

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("음악 설명이 필요합니다.")
        return value


class MusicPromptEnhancementRequest(BaseModel):
    target: Literal["description", "lyrics"]
    description: str = Field(min_length=1, max_length=5000)
    lyrics: str = Field(default="", max_length=5000)
    duration_seconds: float = Field(default=60, ge=10, le=300)
    prompt_output_languages: list[Literal["ko", "en", "ja"]] = Field(
        default_factory=lambda: ["en"], min_length=1, max_length=3
    )

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("음악 설명이 필요합니다.")
        return value

    @field_validator("prompt_output_languages")
    @classmethod
    def unique_prompt_output_languages(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("음악 프롬프트 출력 언어는 중복 선택할 수 없습니다.")
        return value


class MusicPromptEnhancementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contents: str = Field(min_length=1, max_length=5000)


class MusicOutput(BaseModel):
    url: str
    filename: str
    content_type: str
    duration_seconds: float | None = None
    size_bytes: int | None = None


class MusicGenerationAccepted(BaseModel):
    prompt_id: str
    client_id: str
    generation_id: str
    status: Literal["queued"]
    seed: int
    duration_seconds: float
    created_at: datetime
    elapsed_seconds: float = 0


class MusicGenerationStatus(BaseModel):
    prompt_id: str
    generation_id: str
    status: str
    progress: float = Field(default=0, ge=0, le=100)
    queue_position: int | None = Field(default=None, ge=1)
    seed: int | None = None
    requested_duration_seconds: float
    created_at: datetime | None = None
    elapsed_seconds: float = Field(default=0, ge=0)
    audio: MusicOutput | None = None


@router.get("/options", response_model=MusicGenerationOptions)
def music_options(_: UserResponse = Depends(current_user)) -> MusicGenerationOptions:
    try:
        missing_nodes, missing_models = _readiness()
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    missing = [*missing_nodes, *missing_models]
    available = storage_enabled() and not missing
    if missing:
        detail = f"필요한 Music 3 항목이 없습니다: {', '.join(missing)}"
    elif not storage_enabled():
        detail = "스토리지 설정이 없습니다."
    else:
        detail = ""
    return MusicGenerationOptions(model="MiniMax-Music3", service_available=available, detail=detail)


@router.post("/enhance-prompt", response_model=MusicPromptEnhancementResponse)
def enhance_music_prompt(
    payload: MusicPromptEnhancementRequest,
    request: Request,
    _: UserResponse = Depends(current_user),
) -> MusicPromptEnhancementResponse:
    try:
        return _enhance_music_prompt(payload)
    except _VLLMError as exc:
        request.state.provider_response = exc.provider_response
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("", response_model=MusicGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_music(payload: MusicGenerationRequest, user: UserResponse = Depends(current_user)) -> MusicGenerationAccepted:
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    try:
        missing_nodes, missing_models = _readiness()
        if missing_nodes or missing_models:
            raise _ComfyUIError(f"MiniMax-Music3 실행 파일이 준비되지 않았습니다: {', '.join([*missing_nodes, *missing_models])}")
        prompt, seed = _build_prompt(payload)
        client_id = str(uuid.uuid4())
        response = _request_json("POST", "/prompt", {"prompt": prompt, "client_id": client_id})
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise HTTPException(status_code=502, detail="ComfyUI가 음악 생성 작업 ID를 반환하지 않았습니다.")
    generation_id, created_at = create_music_generation(
        user_id=user.id,
        prompt_id=prompt_id,
        client_id=client_id,
        description=payload.description,
        lyrics=payload.lyrics,
        seed=seed,
        max_duration_seconds=payload.duration_seconds,
    )
    return MusicGenerationAccepted(
        prompt_id=prompt_id,
        client_id=client_id,
        generation_id=str(generation_id),
        status="queued",
        seed=seed,
        duration_seconds=payload.duration_seconds,
        created_at=created_at,
    )


@router.get("/latest", response_model=MusicGenerationStatus | None)
def latest_music(user: UserResponse = Depends(current_user)) -> MusicGenerationStatus | None:
    generation = get_latest_music_generation(user.id)
    if generation is None:
        return None
    try:
        return _history_status(generation, user.id)
    except (StorageError, _ComfyUIError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/{prompt_id}", response_model=MusicGenerationStatus)
def music_status(prompt_id: str, user: UserResponse = Depends(current_user)) -> MusicGenerationStatus:
    generation = _require_generation(prompt_id, user.id)
    try:
        return _history_status(generation, user.id)
    except (StorageError, _ComfyUIError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/{prompt_id}/cancel", response_model=MusicGenerationStatus)
def cancel_music(prompt_id: str, user: UserResponse = Depends(current_user)) -> MusicGenerationStatus:
    generation = _require_generation(prompt_id, user.id)
    if generation["status"] == "cancelled":
        return _status_from_row(generation, user.id)
    if generation["status"] not in {"queued", "processing"}:
        return _history_status(generation, user.id)
    try:
        if not cancel_comfy_generation(prompt_id):
            current = _history_status(generation, user.id)
            if current.status in {"completed", "failed", "cancelled"}:
                return current
            raise HTTPException(status_code=409, detail="이미 처리 중인 작업이라 취소할 수 없습니다.")
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    update_music_generation_status(prompt_id=prompt_id, user_id=user.id, status="cancelled")
    current = get_music_generation(prompt_id, user.id) or generation
    result = _status_from_row(current, user.id)
    generation_event_broker.publish(
        key=generation_key("music", user.id, prompt_id),
        event="cancelled",
        data=result.model_dump(mode="json"),
    )
    return result


@router.get("/{prompt_id}/events")
async def music_events(
    prompt_id: str,
    client_id: str = Query(min_length=1, max_length=128),
    user: UserResponse = Depends(current_user),
) -> StreamingResponse:
    generation = _require_generation(prompt_id, user.id)
    if generation["client_id"] != client_id:
        raise HTTPException(status_code=404, detail="음악 생성 결과를 찾을 수 없습니다.")
    return StreamingResponse(
        _stream_events(prompt_id, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


async def _stream_events(prompt_id: str, user_id: uuid.UUID):
    key = generation_key("music", user_id, prompt_id)
    async with generation_event_broker.subscribe(key) as events:
        generation = await asyncio.to_thread(get_music_generation, prompt_id, user_id)
        if generation is None:
            yield _sse("failed", {"prompt_id": prompt_id, "status": "failed", "message": "음악 생성 결과를 찾을 수 없습니다."})
            return
        try:
            current = await asyncio.to_thread(_history_status, generation, user_id)
        except (StorageError, _ComfyUIError) as exc:
            yield _sse("error", {"prompt_id": prompt_id, "message": str(exc)})
            return
        event = current.status if current.status in {"completed", "failed", "cancelled"} else "status"
        yield _sse(event, current.model_dump(mode="json"))
        if event != "status":
            return
        while True:
            try:
                message = await asyncio.wait_for(events.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield _sse(message["event"], message["data"])
            if message["event"] in {"completed", "failed", "cancelled", "error"}:
                return


def _music_prompt_pattern(languages: Sequence[str]) -> str:
    if not languages or any(language not in _MUSIC_PROMPT_LANGUAGE_CHARS for language in languages):
        raise ValueError("지원하지 않는 음악 프롬프트 출력 언어입니다.")
    language_chars = "".join(_MUSIC_PROMPT_LANGUAGE_CHARS[language] for language in dict.fromkeys(languages))
    visible_language_chars = "".join(
        _MUSIC_PROMPT_NON_WHITESPACE_LANGUAGE_CHARS[language] for language in dict.fromkeys(languages)
    )
    content = rf"(?:[{_MUSIC_PROMPT_COMMON_CHARS}{language_chars}]|{_MUSIC_PROMPT_FIXED_TOKENS})"
    visible = rf"(?:[{_MUSIC_PROMPT_NON_WHITESPACE_COMMON_CHARS}{visible_language_chars}]|{_MUSIC_PROMPT_FIXED_TOKENS})"
    return rf"^{visible}(?:{content}*{visible})?$"


def _music_prompt_schema(languages: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "contents": {
                "type": "string",
                "minLength": 1,
                "maxLength": 5000,
                "pattern": _music_prompt_pattern(languages),
            }
        },
        "required": ["contents"],
        "additionalProperties": False,
    }


def _enhance_music_prompt(payload: MusicPromptEnhancementRequest) -> MusicPromptEnhancementResponse:
    system_prompt = (
        MUSIC_DESCRIPTION_ENHANCEMENT_SYSTEM_PROMPT
        if payload.target == "description"
        else MUSIC_LYRICS_ENHANCEMENT_SYSTEM_PROMPT
    )
    result = _request_structured_object(
        system_prompt=system_prompt,
        user_prompt=MUSIC_PROMPT_ENHANCEMENT_USER_PROMPT.format(
            target=payload.target,
            description=payload.description,
            lyrics=payload.lyrics.strip(),
            duration=f"{payload.duration_seconds:g}",
            languages=", ".join(_MUSIC_PROMPT_LANGUAGE_NAMES[language] for language in payload.prompt_output_languages),
        ),
        max_tokens=_MUSIC_PROMPT_MAX_TOKENS,
        temperature=0.6,
        timeout_seconds=_MUSIC_PROMPT_TIMEOUT_SECONDS,
        schema=_music_prompt_schema(payload.prompt_output_languages),
        name=f"music_{payload.target}",
    )
    try:
        response = MusicPromptEnhancementResponse.model_validate(result)
    except ValidationError as exc:
        raise _VLLMError("vLLM 구조화 음악 프롬프트에 contents가 없습니다.") from exc
    return response.model_copy(update={"contents": response.contents.strip()})


def _build_prompt(request: MusicGenerationRequest) -> tuple[dict[str, Any], int]:
    try:
        prompt = json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("MiniMax-Music3 workflow를 읽을 수 없습니다.") from exc
    seed = request.seed if request.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    prompt["4"]["inputs"].update(
        caption=request.description,
        lyrics=request.lyrics,
        seed=seed,
        max_duration=request.duration_seconds,
    )
    prompt["7"]["inputs"]["seed"] = seed
    prompt["9"]["inputs"]["filename_prefix"] = f"LocalField_Music3_{uuid.uuid4().hex[:12]}"
    return prompt, seed


def _readiness() -> tuple[list[str], list[str]]:
    object_info = _request_json("GET", "/object_info")
    try:
        workflow = json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("MiniMax-Music3 workflow를 읽을 수 없습니다.") from exc
    missing_nodes = sorted({node["class_type"] for node in workflow.values()} - object_info.keys())
    missing_models: list[str] = []
    for (node_type, input_name), model_name in _MODEL_FILES.items():
        try:
            choices = object_info[node_type]["input"]["required"][input_name][0]
        except (IndexError, KeyError, TypeError):
            choices = []
        if not isinstance(choices, list) or model_name not in choices:
            missing_models.append(model_name)
    return missing_nodes, missing_models


def _history_status(generation: dict[str, Any], user_id: uuid.UUID) -> MusicGenerationStatus:
    if generation["status"] in {"completed", "failed", "cancelled"}:
        return _status_from_row(generation, user_id)
    prompt_id = generation["prompt_id"]
    history = _request_json("GET", f"/history/{prompt_id}")
    entry = history.get(prompt_id)
    progress = generation_progress(prompt_id, user_id)
    if not isinstance(entry, dict):
        current_status = progress["status"] or "queued"
        update_music_generation_status(prompt_id=prompt_id, user_id=user_id, status=current_status)
        current = get_music_generation(prompt_id, user_id) or generation
        return _status_from_row(current, user_id, progress=progress)
    raw_status = entry.get("status")
    comfy_status = raw_status if isinstance(raw_status, dict) else {}
    if str(comfy_status.get("status_str", "")) in {"error", "failed"}:
        update_music_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
        current = get_music_generation(prompt_id, user_id) or generation
        return _status_from_row(current, user_id, progress=progress)
    if comfy_status.get("completed") is True:
        _sync_audio_output(generation, _raw_audio_output(entry.get("outputs")), user_id)
        current = get_music_generation(prompt_id, user_id) or generation
        return _status_from_row(current, user_id, progress={"progress": 100, "queue_position": None})
    update_music_generation_status(prompt_id=prompt_id, user_id=user_id, status="processing")
    current = get_music_generation(prompt_id, user_id) or generation
    return _status_from_row(current, user_id, progress=progress)


def _raw_audio_output(outputs: Any) -> dict[str, str] | None:
    if not isinstance(outputs, dict):
        return None
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        audios = output.get("audio") or output.get("audios")
        if not isinstance(audios, list):
            continue
        for audio in audios:
            if not isinstance(audio, dict):
                continue
            filename = audio.get("filename")
            subfolder = audio.get("subfolder", "")
            file_type = audio.get("type", "output")
            if isinstance(filename, str) and Path(filename).suffix.lower() in _AUDIO_TYPES and isinstance(subfolder, str) and isinstance(file_type, str):
                return {"filename": filename, "subfolder": subfolder, "type": file_type}
    return None


def _sync_audio_output(generation: dict[str, Any], audio: dict[str, str] | None, user_id: uuid.UUID) -> None:
    if generation.get("storage_file_id"):
        update_music_generation_status(prompt_id=generation["prompt_id"], user_id=user_id, status="completed")
        return
    if audio is None:
        update_music_generation_status(prompt_id=generation["prompt_id"], user_id=user_id, status="failed")
        raise _ComfyUIError("ComfyUI가 음악 결과를 반환하지 않았습니다.")
    query = urlencode({"filename": audio["filename"], "subfolder": audio["subfolder"], "type": audio["type"]})
    content, _ = _request_bytes(f"/view?{query}")
    suffix = Path(audio["filename"]).suffix.lower()
    if not _valid_audio_magic(content, suffix):
        update_music_generation_status(prompt_id=generation["prompt_id"], user_id=user_id, status="failed")
        raise _ComfyUIError("ComfyUI 음악 결과 형식이 올바르지 않습니다.")
    try:
        storage_file_id = storage_upload_file(content=content, media_type=_AUDIO_TYPES[suffix], owner_id=str(user_id))
    except StorageError:
        update_music_generation_status(prompt_id=generation["prompt_id"], user_id=user_id, status="failed")
        raise
    update_music_generation_status(
        prompt_id=generation["prompt_id"],
        user_id=user_id,
        status="completed",
        storage_file_id=storage_file_id,
        filename=audio["filename"],
        content_type=_AUDIO_TYPES[suffix],
        size_bytes=len(content),
    )


def _valid_audio_magic(content: bytes, suffix: str) -> bool:
    if suffix == ".flac":
        return content.startswith(b"fLaC")
    if suffix == ".wav":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WAVE"
    if suffix == ".mp3":
        return content.startswith(b"ID3") or (len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0)
    if suffix in {".ogg", ".opus"}:
        return content.startswith(b"OggS")
    return False


def _status_from_row(
    generation: dict[str, Any],
    user_id: uuid.UUID,
    *,
    progress: dict[str, Any] | None = None,
) -> MusicGenerationStatus:
    progress = progress or generation_progress(generation["prompt_id"], user_id)
    output = None
    file_id = generation.get("storage_file_id")
    filename = generation.get("filename")
    content_type = generation.get("content_type")
    if generation["status"] == "completed" and isinstance(file_id, str) and isinstance(filename, str) and isinstance(content_type, str):
        output = MusicOutput(
            url=storage_read_url(file_id=file_id, owner_id=str(user_id)),
            filename=filename,
            content_type=content_type,
            duration_seconds=generation.get("duration_seconds"),
            size_bytes=int(generation.get("size_bytes") or 0) or None,
        )
    return MusicGenerationStatus(
        prompt_id=generation["prompt_id"],
        generation_id=str(generation["id"]),
        status=generation["status"],
        progress=100 if generation["status"] == "completed" else float(progress.get("progress", 0)),
        queue_position=progress.get("queue_position") or (
            _queue_position(generation["prompt_id"])
            if generation["status"] in {"queued", "processing"}
            else None
        ),
        seed=generation.get("seed"),
        requested_duration_seconds=float(generation.get("max_duration_seconds") or 60),
        created_at=generation.get("created_at"),
        elapsed_seconds=generation_elapsed_seconds(generation),
        audio=output,
    )


def _require_generation(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any]:
    generation = get_music_generation(prompt_id, user_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="음악 생성 결과를 찾을 수 없습니다.")
    return generation


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
