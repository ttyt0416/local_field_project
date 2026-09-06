from __future__ import annotations

import asyncio
import copy
from datetime import datetime
import json
import re
import secrets
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, ValidationError, model_validator
from starlette.responses import StreamingResponse

from .auth import UserResponse, current_user
from .comfyui import (
    _ComfyUIError,
    _queue_position,
    _request_bytes,
    _request_json,
    cancel_comfy_generation,
    generation_node,
    generation_progress,
)
from .database import (
    create_media_asset,
    create_three_d_generation,
    generation_elapsed_seconds,
    get_reusable_media,
    get_three_d_generation,
    update_three_d_generation_status,
)
from .generation_events import generation_event_broker, generation_key
from .storage import (
    StorageError,
    download_file as storage_download_file,
    enabled as storage_enabled,
    read_url as storage_read_url,
    upload_file as storage_upload_file,
)
from .video import VideoAsset, _ResolvedAsset, _asset_cache_key, _safe_filename, _upload_to_comfy


router = APIRouter(prefix="/generation/3d", tags=["3D generation"])
_WORKFLOW_PATH = Path(__file__).with_name("workflows") / "trellis2.json"
_MAX_INPUT_SIZE = 50 * 1024 * 1024
# ponytail: keep seeds JSON-safe until the API and UI carry them as strings end to end.
_MAX_SEED = 2**53 - 1
_FILE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

_PRESETS: dict[str, dict[str, int | str]] = {
    "preview": {
        "target_resolution": "1024",
        "target_face_count": 150_000,
        "texture_resolution": 1024,
        "remesh_resolution": 384,
        "normal_resolution": 1024,
        "ao_resolution": 512,
    },
    "standard": {
        "target_resolution": "1024",
        "target_face_count": 350_000,
        "texture_resolution": 2048,
        "remesh_resolution": 512,
        "normal_resolution": 2048,
        "ao_resolution": 1024,
    },
    "high": {
        "target_resolution": "1536",
        "target_face_count": 700_000,
        "texture_resolution": 4096,
        "remesh_resolution": 768,
        "normal_resolution": 2048,
        "ao_resolution": 1024,
    },
}
_REQUIRED_MODELS = {
    ("UNETLoader", "unet_name"): "trellis_2_int8_convrot.safetensors",
    ("CLIPVisionLoader", "clip_name"): "dino_v3_vit_l.safetensors",
    ("VAELoader", "vae_name"): "trellis_2_shape_vae_bf16.safetensors",
    ("VAELoader", "vae_name#texture"): "trellis_2_texture_vae_bf16.safetensors",
    ("LoadBackgroundRemovalModel", "bg_removal_name"): "birefnet.safetensors",
}
_STAGE_BY_NODE = {
    **{node: "background_cleanup" for node in ("122", "193", "28", "248", "312")},
    **{node: "structure" for node in ("15", "20", "25", "40", "80", "81", "83", "3")},
    **{node: "shape" for node in ("18", "22", "23", "64", "91", "92", "94", "117")},
    **{node: "texture" for node in ("12", "93", "98", "118")},
}


class ThreeDSource(BaseModel):
    file_id: str | None = Field(default=None, max_length=64)
    file_index: int | None = Field(default=None, ge=0, le=0)

    @model_validator(mode="after")
    def validate_source(self) -> "ThreeDSource":
        if (self.file_id is None) == (self.file_index is None):
            raise ValueError("Storage file_id 또는 새 파일 index 중 하나가 필요합니다.")
        return self


class ThreeDGenerationRequest(BaseModel):
    source: ThreeDSource
    preset: Literal["preview", "standard", "high"] = "standard"
    seed: int | None = Field(default=None, ge=0, le=_MAX_SEED)
    remove_background: bool = True
    padding: float = Field(default=1.1, ge=1.0, le=1.5)


class ThreeDModelOutput(BaseModel):
    url: str
    filename: str
    size_bytes: int | None = None


class ThreeDGenerationAccepted(BaseModel):
    prompt_id: str
    client_id: str
    generation_id: str
    status: Literal["queued"]
    stage: Literal["queued"] = "queued"
    progress: float = 0
    preset: str
    seed: int
    created_at: datetime
    elapsed_seconds: float = 0


class ThreeDGenerationStatus(BaseModel):
    prompt_id: str
    status: str
    stage: str
    progress: float = Field(default=0, ge=0, le=100)
    queue_position: int | None = Field(default=None, ge=1)
    created_at: datetime | None = None
    elapsed_seconds: float = Field(default=0, ge=0)
    model: ThreeDModelOutput | None = None


class ThreeDOptions(BaseModel):
    ready: bool
    missing_nodes: list[str]
    missing_models: list[str]
    presets: dict[str, dict[str, int | str]]


@router.get("/options", response_model=ThreeDOptions)
def three_d_options(_: UserResponse = Depends(current_user)) -> ThreeDOptions:
    try:
        missing_nodes, missing_models = _readiness()
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return ThreeDOptions(
        ready=not missing_nodes and not missing_models,
        missing_nodes=missing_nodes,
        missing_models=missing_models,
        presets=_PRESETS,
    )


@router.post("", response_model=ThreeDGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_three_d(
    payload: str = Form(...),
    files: list[UploadFile] = File(default_factory=list),
    user: UserResponse = Depends(current_user),
) -> ThreeDGenerationAccepted:
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    try:
        request = ThreeDGenerationRequest.model_validate_json(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="3D 생성 입력 JSON이 올바르지 않습니다.") from exc
    _validate_source(request.source, files)
    try:
        missing_nodes, missing_models = _readiness()
        if missing_nodes or missing_models:
            missing = ", ".join([*missing_nodes, *missing_models])
            raise _ComfyUIError(f"TRELLIS.2 실행 파일이 준비되지 않았습니다: {missing}")
        resolved = await _resolve_source(request.source, files, user)
        source_asset = VideoAsset(
            kind="image", file_id=request.source.file_id, file_index=request.source.file_index
        )
        source_key = _asset_cache_key(source_asset)
        comfy_filename = _upload_to_comfy({source_key: resolved}, source_asset, "image")
        prompt, seed = _build_prompt(request, comfy_filename)
        client_id = str(uuid.uuid4())
        response = _request_json("POST", "/prompt", {"prompt": prompt, "client_id": client_id})
    except (StorageError, _ComfyUIError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise HTTPException(status_code=502, detail="ComfyUI가 3D 생성 작업 ID를 반환하지 않았습니다.")
    generation_id, created_at = create_three_d_generation(
        user_id=user.id,
        prompt_id=prompt_id,
        client_id=client_id,
        preset=request.preset,
        seed=seed,
        remove_background=request.remove_background,
        padding=request.padding,
        source_file_id=resolved.file_id,
        source_filename=resolved.filename,
    )
    return ThreeDGenerationAccepted(
        prompt_id=prompt_id,
        client_id=client_id,
        generation_id=str(generation_id),
        status="queued",
        preset=request.preset,
        seed=seed,
        created_at=created_at,
    )


@router.get("/{prompt_id}", response_model=ThreeDGenerationStatus)
def three_d_status(
    prompt_id: str,
    user: UserResponse = Depends(current_user),
) -> ThreeDGenerationStatus:
    generation = _require_generation(prompt_id, user.id)
    try:
        return _history_status(generation, user.id)
    except (StorageError, _ComfyUIError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/{prompt_id}/cancel", response_model=ThreeDGenerationStatus)
def cancel_three_d(
    prompt_id: str,
    user: UserResponse = Depends(current_user),
) -> ThreeDGenerationStatus:
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
    update_three_d_generation_status(
        prompt_id=prompt_id, user_id=user.id, status="cancelled", stage="cancelled"
    )
    cancelled = get_three_d_generation(prompt_id, user.id) or generation
    result = _status_from_row(cancelled, user.id)
    generation_event_broker.publish(
        key=generation_key("3d", user.id, prompt_id),
        event="cancelled",
        data=result.model_dump(mode="json"),
    )
    return result


@router.get("/{prompt_id}/events")
async def three_d_events(
    prompt_id: str,
    client_id: str = Query(min_length=1, max_length=128),
    user: UserResponse = Depends(current_user),
) -> StreamingResponse:
    generation = _require_generation(prompt_id, user.id)
    if generation["client_id"] != client_id:
        raise HTTPException(status_code=404, detail="3D 생성 결과를 찾을 수 없습니다.")
    return StreamingResponse(
        _stream_events(prompt_id, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


async def _stream_events(prompt_id: str, user_id: uuid.UUID):
    key = generation_key("3d", user_id, prompt_id)
    async with generation_event_broker.subscribe(key) as events:
        generation = await asyncio.to_thread(get_three_d_generation, prompt_id, user_id)
        if generation is None:
            yield _sse("failed", {"prompt_id": prompt_id, "status": "failed", "message": "3D 생성 결과를 찾을 수 없습니다."})
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


def _validate_source(source: ThreeDSource, files: list[UploadFile]) -> None:
    if len(files) > 1:
        raise HTTPException(status_code=422, detail="3D 생성에는 이미지 한 장만 사용할 수 있습니다.")
    if source.file_index is not None:
        if len(files) != 1:
            raise HTTPException(status_code=422, detail="선택한 새 이미지를 찾을 수 없습니다.")
        if not (files[0].content_type or "").lower().startswith("image/"):
            raise HTTPException(status_code=415, detail="이미지 파일만 사용할 수 있습니다.")
    elif not _FILE_ID_PATTERN.fullmatch(source.file_id or ""):
        raise HTTPException(status_code=422, detail="Storage file_id 형식이 올바르지 않습니다.")


async def _resolve_source(source: ThreeDSource, files: list[UploadFile], user: UserResponse) -> _ResolvedAsset:
    if source.file_id:
        record = get_reusable_media(source.file_id, user.id)
        if record is None or record["media_kind"] != "image":
            raise HTTPException(status_code=404, detail="선택한 이미지를 찾을 수 없습니다.")
        content, stored_type = storage_download_file(file_id=source.file_id, owner_id=str(user.id))
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
        return _ResolvedAsset(
            file_id=source.file_id,
            filename=record["filename"],
            content=content,
            media_type=media_type,
            kind="image",
        )

    upload = files[0]
    content = await upload.read(_MAX_INPUT_SIZE + 1)
    if len(content) > _MAX_INPUT_SIZE:
        raise HTTPException(status_code=413, detail="3D 입력 이미지는 50MB 이하여야 합니다.")
    if not content:
        raise HTTPException(status_code=422, detail="빈 이미지 파일은 사용할 수 없습니다.")
    filename = _safe_filename(upload.filename, "image", upload.content_type)
    media_type = upload.content_type or "image/png"
    file_id = storage_upload_file(content=content, media_type=media_type, owner_id=str(user.id))
    create_media_asset(
        user_id=user.id,
        storage_file_id=file_id,
        filename=filename,
        content_type=media_type,
        media_kind="image",
        size=len(content),
    )
    return _ResolvedAsset(
        file_id=file_id,
        filename=filename,
        content=content,
        media_type=media_type,
        kind="image",
    )


def _build_prompt(request: ThreeDGenerationRequest, comfy_filename: str) -> tuple[dict[str, Any], int]:
    try:
        prompt = json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("TRELLIS.2 workflow를 읽을 수 없습니다.") from exc
    prompt = copy.deepcopy(prompt)
    preset = _PRESETS[request.preset]
    seed = request.seed if request.seed is not None else secrets.randbelow(_MAX_SEED + 1)
    prompt["122"]["inputs"]["image"] = comfy_filename
    prompt["248"]["inputs"]["switch"] = request.remove_background
    prompt["312"]["inputs"]["pad_factor"] = request.padding
    prompt["94"]["inputs"]["target_resolution"] = preset["target_resolution"]
    prompt["186"]["inputs"]["target_face_count"] = preset["target_face_count"]
    prompt["288"]["inputs"]["value"] = preset["texture_resolution"]
    prompt["241"]["inputs"]["resolution"] = preset["remesh_resolution"]
    prompt["224"]["inputs"]["resolution"] = preset["normal_resolution"]
    prompt["233"]["inputs"]["resolution"] = preset["ao_resolution"]
    prompt["900"]["inputs"]["filename_prefix"] = f"LocalField_3D_{uuid.uuid4().hex[:12]}"
    for node in prompt.values():
        if node.get("class_type") == "KSampler":
            node["inputs"]["seed"] = seed
    return prompt, seed


def _readiness() -> tuple[list[str], list[str]]:
    object_info = _request_json("GET", "/object_info")
    try:
        workflow = json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("TRELLIS.2 workflow를 읽을 수 없습니다.") from exc
    required_nodes = sorted({node["class_type"] for node in workflow.values()})
    missing_nodes = [node for node in required_nodes if node not in object_info]
    missing_models: list[str] = []
    for (node_type, input_key), model_name in _REQUIRED_MODELS.items():
        schema_key = input_key.split("#", 1)[0]
        node = object_info.get(node_type)
        try:
            specification = node["input"]["required"][schema_key] if isinstance(node, dict) else []
            if isinstance(specification[0], list):
                choices = specification[0]
            elif len(specification) > 1 and isinstance(specification[1], dict):
                choices = specification[1].get("options", [])
            else:
                choices = []
        except (IndexError, KeyError, TypeError):
            choices = []
        if not isinstance(choices, list) or model_name not in choices:
            missing_models.append(model_name)
    return missing_nodes, list(dict.fromkeys(missing_models))


def _history_status(generation: dict[str, Any], user_id: uuid.UUID) -> ThreeDGenerationStatus:
    if generation["status"] == "cancelled":
        return _status_from_row(generation, user_id)
    prompt_id = generation["prompt_id"]
    history = _request_json("GET", f"/history/{prompt_id}")
    entry = history.get(prompt_id)
    progress = generation_progress(prompt_id, user_id)
    node = generation_node(prompt_id, user_id)
    if not isinstance(entry, dict):
        current_status = progress["status"] or "queued"
        stage = _stage_for(node, generation["stage"], current_status)
        update_three_d_generation_status(
            prompt_id=prompt_id, user_id=user_id, status=current_status, stage=stage
        )
        current = get_three_d_generation(prompt_id, user_id) or generation
        return _status_from_row(current, user_id, progress=progress)

    raw_status = entry.get("status")
    comfy_status = raw_status if isinstance(raw_status, dict) else {}
    if str(comfy_status.get("status_str", "")) in {"error", "failed"}:
        update_three_d_generation_status(
            prompt_id=prompt_id, user_id=user_id, status="failed", stage="failed"
        )
        current = get_three_d_generation(prompt_id, user_id) or generation
        return _status_from_row(current, user_id, progress=progress)
    if comfy_status.get("completed") is True:
        raw_model = _raw_model_output(entry.get("outputs"))
        _sync_model_output(generation, raw_model, user_id)
        current = get_three_d_generation(prompt_id, user_id) or generation
        return _status_from_row(current, user_id, progress={"progress": 100, "queue_position": None})

    stage = _stage_for(node, generation["stage"], "processing")
    update_three_d_generation_status(
        prompt_id=prompt_id, user_id=user_id, status="processing", stage=stage
    )
    current = get_three_d_generation(prompt_id, user_id) or generation
    return _status_from_row(current, user_id, progress=progress)


def _raw_model_output(outputs: Any) -> dict[str, str] | None:
    if not isinstance(outputs, dict):
        return None
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        models = output.get("3d")
        if not isinstance(models, list):
            continue
        for model in models:
            if not isinstance(model, dict):
                continue
            filename = model.get("filename")
            subfolder = model.get("subfolder", "")
            model_type = model.get("type", "output")
            if (
                isinstance(filename, str)
                and filename.lower().endswith(".glb")
                and isinstance(subfolder, str)
                and isinstance(model_type, str)
            ):
                return {"filename": filename, "subfolder": subfolder, "type": model_type}
    return None


def _sync_model_output(generation: dict[str, Any], model: dict[str, str] | None, user_id: uuid.UUID) -> None:
    if generation.get("storage_file_id"):
        update_three_d_generation_status(
            prompt_id=generation["prompt_id"], user_id=user_id, status="completed", stage="completed"
        )
        return
    if model is None:
        update_three_d_generation_status(
            prompt_id=generation["prompt_id"], user_id=user_id, status="failed", stage="failed"
        )
        raise _ComfyUIError("ComfyUI가 GLB 결과를 반환하지 않았습니다.")
    update_three_d_generation_status(
        prompt_id=generation["prompt_id"], user_id=user_id, status="processing", stage="storage"
    )
    query = urlencode(
        {"filename": model["filename"], "subfolder": model["subfolder"], "type": model["type"]}
    )
    content, _ = _request_bytes(f"/view?{query}")
    if len(content) < 12 or content[:4] != b"glTF":
        update_three_d_generation_status(
            prompt_id=generation["prompt_id"], user_id=user_id, status="failed", stage="failed"
        )
        raise _ComfyUIError("ComfyUI GLB 결과 형식이 올바르지 않습니다.")
    try:
        storage_file_id = storage_upload_file(
            content=content, media_type="model/gltf-binary", owner_id=str(user_id)
        )
    except StorageError:
        update_three_d_generation_status(
            prompt_id=generation["prompt_id"], user_id=user_id, status="failed", stage="failed"
        )
        raise
    update_three_d_generation_status(
        prompt_id=generation["prompt_id"],
        user_id=user_id,
        status="completed",
        stage="completed",
        storage_file_id=storage_file_id,
        filename=model["filename"],
        subfolder=model["subfolder"],
        model_type=model["type"],
        size_bytes=len(content),
    )


def _status_from_row(
    generation: dict[str, Any],
    user_id: uuid.UUID,
    *,
    progress: dict[str, Any] | None = None,
) -> ThreeDGenerationStatus:
    progress = progress or generation_progress(generation["prompt_id"], user_id)
    output = None
    file_id = generation.get("storage_file_id")
    filename = generation.get("filename")
    if generation["status"] == "completed" and isinstance(file_id, str) and isinstance(filename, str):
        output = ThreeDModelOutput(
            url=storage_read_url(file_id=file_id, owner_id=str(user_id)),
            filename=filename,
            size_bytes=int(generation.get("size_bytes") or 0) or None,
        )
    created_at = generation.get("created_at")
    return ThreeDGenerationStatus(
        prompt_id=generation["prompt_id"],
        status=generation["status"],
        stage=generation["stage"],
        progress=100 if generation["status"] == "completed" else float(progress.get("progress", 0)),
        queue_position=progress.get("queue_position") or (
            _queue_position(generation["prompt_id"])
            if generation["status"] in {"queued", "processing"}
            else None
        ),
        created_at=created_at,
        elapsed_seconds=generation_elapsed_seconds(generation),
        model=output,
    )


def _stage_for(node: Any, stored_stage: str, current_status: str) -> str:
    if current_status == "queued":
        return "queued"
    if isinstance(node, str):
        return _STAGE_BY_NODE.get(node, "mesh")
    return stored_stage if stored_stage not in {"queued", "completed"} else "structure"


def _require_generation(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any]:
    generation = get_three_d_generation(prompt_id, user_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="3D 생성 결과를 찾을 수 없습니다.")
    return generation


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
