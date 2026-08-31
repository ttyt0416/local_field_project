from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request as UrlRequest
from urllib.request import build_opener
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .auth import UserResponse, current_user
from .configs.constants import settings
from .database import (
    cancel_model_download,
    claim_model_download,
    complete_model_download,
    create_model_download,
    fail_model_download,
    is_model_download_active,
    list_model_downloads,
    reset_model_downloads,
    retry_model_download,
    update_model_download_progress,
)


router = APIRouter(prefix="/models", tags=["model downloads"])
ModelType = Literal["checkpoint", "diffusion_model", "lora", "text_encoder", "vae", "embedding"]
_MODEL_TARGETS: dict[ModelType, tuple[str, str]] = {
    "checkpoint": ("체크포인트", "checkpoints"),
    "diffusion_model": ("Diffusion Model", "diffusion_models"),
    "lora": ("LoRA", "loras"),
    "text_encoder": ("텍스트 인코더", "text_encoders"),
    "vae": ("VAE", "vae"),
    "embedding": ("임베딩", "embeddings"),
}
_MODEL_EXTENSIONS = {".ckpt", ".pt", ".pt2", ".bin", ".pth", ".safetensors", ".pkl", ".sft"}
_CIVITAI_API_BASE = "https://civitai.com/api/v1"
_CIVITAI_HOST = "civitai.com"
_CIVITAI_SOURCE_HOSTS = {"civitai.com", "www.civitai.com", "civitai.red", "www.civitai.red"}
_DOWNLOAD_REDIRECT_CODES = {301, 302, 303, 307, 308}
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_DOWNLOAD_PROGRESS_INTERVAL = 1.0
_DOWNLOAD_MAX_REDIRECTS = 5


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


class CivitaiError(RuntimeError):
    def __init__(self, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY) -> None:
        super().__init__(message)
        self.status_code = status_code


class _ModelDownloadCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class CivitaiFile:
    name: str
    file_type: str
    download_url: str
    size_bytes: int | None
    sha256: str | None
    primary: bool


@dataclass(frozen=True)
class CivitaiVersion:
    version_id: int
    model_id: int | None
    model_name: str
    model_type: str
    version_name: str
    base_model: str | None
    files: tuple[CivitaiFile, ...]
    published_at: datetime | None = None


class CivitaiFileResponse(BaseModel):
    index: int
    name: str
    file_type: str
    size_bytes: int | None
    sha256: str | None
    primary: bool


class CivitaiVersionOption(BaseModel):
    version_id: int
    version_name: str
    base_model: str | None
    published_at: datetime | None


class CivitaiLookupResponse(BaseModel):
    version_id: int
    model_id: int | None
    model_name: str
    model_type: str
    version_name: str
    base_model: str | None
    target_model_type: ModelType
    suggested_subfolder: str
    files: list[CivitaiFileResponse]
    selected_file_index: int
    versions: list[CivitaiVersionOption]


class ModelDownloadRequest(BaseModel):
    source: str = Field(min_length=1, max_length=2048)
    model_type: ModelType
    file_index: int | None = Field(default=None, ge=0)
    subfolder: str = Field(default="", max_length=255)


class ModelDownloadResponse(BaseModel):
    id: str
    version_id: int
    model_type: ModelType
    subfolder: str
    filename: str
    status: str
    downloaded_bytes: int
    total_bytes: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class InstalledModelResponse(BaseModel):
    model_type: ModelType
    filename: str
    size_bytes: int
    modified_at: datetime


class ModelFolderRequest(BaseModel):
    model_type: ModelType
    parent: str = Field(default="", max_length=255)
    name: str = Field(min_length=1, max_length=120)


class ModelFolderResponse(BaseModel):
    model_type: ModelType
    subfolder: str


class MoveInstalledModelRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    subfolder: str = Field(default="", max_length=255)


@router.get("/installed", response_model=list[InstalledModelResponse])
def installed_models(_: UserResponse = Depends(current_user)) -> list[InstalledModelResponse]:
    root = Path(settings.comfyui_models_path)
    result: list[InstalledModelResponse] = []
    for model_type, target in _MODEL_TARGETS.items():
        folder_name = target[1]
        directory = root / folder_name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in _MODEL_EXTENSIONS:
                continue
            try:
                file_stat = path.stat()
            except OSError:
                continue
            result.append(
                InstalledModelResponse(
                    model_type=model_type,
                    filename=str(path.relative_to(directory)),
                    size_bytes=file_stat.st_size,
                    modified_at=datetime.fromtimestamp(file_stat.st_mtime, timezone.utc),
                )
            )
    return sorted(result, key=lambda item: (item.model_type, item.filename.casefold()))


@router.delete("/installed/{model_type}/{filename:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_installed_model(
    model_type: ModelType,
    filename: str,
    _: UserResponse = Depends(current_user),
) -> None:
    target = _installed_model_path(model_type, filename)
    if not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="설치된 모델 파일을 찾을 수 없습니다.")
    try:
        target.unlink()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="설치된 모델 파일을 찾을 수 없습니다.") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="모델 파일을 삭제할 수 없습니다.") from exc


@router.post("/installed/{model_type}/move", response_model=InstalledModelResponse)
def move_installed_model(
    model_type: ModelType,
    payload: MoveInstalledModelRequest,
    _: UserResponse = Depends(current_user),
) -> InstalledModelResponse:
    source = _installed_model_path(model_type, payload.filename)
    if not source.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="설치된 모델 파일을 찾을 수 없습니다.")
    try:
        subfolder = _safe_folder_selection(payload.subfolder)
        destination_directory = _model_target_directory(model_type, subfolder)
    except CivitaiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if not destination_directory.is_dir():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="선택한 모델 폴더를 찾을 수 없습니다.")
    destination = destination_directory / source.name
    if destination == source:
        file_stat = source.stat()
        return InstalledModelResponse(
            model_type=model_type,
            filename=payload.filename,
            size_bytes=file_stat.st_size,
            modified_at=datetime.fromtimestamp(file_stat.st_mtime, timezone.utc),
        )
    if destination.exists() or destination.is_symlink():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="대상 폴더에 같은 이름의 모델 파일이 이미 있습니다.")
    try:
        source.rename(destination)
        verified = _installed_model_path(model_type, f"{subfolder}/{source.name}" if subfolder else source.name)
        file_stat = verified.stat()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="설치된 모델 파일을 찾을 수 없습니다.") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="모델 파일을 이동할 수 없습니다.") from exc
    return InstalledModelResponse(
        model_type=model_type,
        filename=str(verified.relative_to(_model_target_directory(model_type, ""))),
        size_bytes=file_stat.st_size,
        modified_at=datetime.fromtimestamp(file_stat.st_mtime, timezone.utc),
    )


def _installed_model_path(model_type: ModelType, filename: str) -> Path:
    root = Path(settings.comfyui_models_path).resolve()
    directory = (root / _MODEL_TARGETS[model_type][1]).resolve()
    if not filename.strip() or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="모델 파일 경로가 올바르지 않습니다.")
    try:
        directory.relative_to(root)
        candidate = directory / filename
        current = directory
        for component in Path(filename).parts:
            current /= component
            if current.is_symlink():
                raise ValueError("symbolic link")
        target = candidate.resolve()
        target.relative_to(directory)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="모델 파일 경로가 올바르지 않습니다.") from exc
    if target == directory or target.suffix.casefold() not in _MODEL_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="삭제할 수 없는 모델 파일입니다.")
    return candidate


@router.get("/folders", response_model=list[ModelFolderResponse])
def list_model_folders(
    model_type: ModelType = Query(...),
    _: UserResponse = Depends(current_user),
) -> list[ModelFolderResponse]:
    base = _model_target_directory(model_type, "")
    folders = [""]
    if base.is_dir():
        for path in base.rglob("*"):
            if not path.is_dir() or path.is_symlink():
                continue
            try:
                relative = path.relative_to(base).as_posix()
                if any(part.startswith(".") for part in Path(relative).parts):
                    continue
                _model_target_directory(model_type, relative)
            except (CivitaiError, ValueError):
                continue
            folders.append(relative)
    return [ModelFolderResponse(model_type=model_type, subfolder=folder) for folder in sorted(folders)]


@router.post("/folders", response_model=ModelFolderResponse, status_code=status.HTTP_201_CREATED)
def create_model_folder(
    payload: ModelFolderRequest,
    _: UserResponse = Depends(current_user),
) -> ModelFolderResponse:
    try:
        parent = _safe_folder_selection(payload.parent) if payload.parent else ""
        name = payload.name.strip()
        if (
            not name
            or name in {".", ".."}
            or name.startswith(".")
            or "/" in name
            or "\\" in name
            or any(ord(character) < 32 for character in name)
        ):
            raise CivitaiError("새 폴더 이름이 올바르지 않습니다.", status_code=status.HTTP_400_BAD_REQUEST)
        parent_path = _model_target_directory(payload.model_type, parent)
        if not parent_path.is_dir():
            raise CivitaiError("상위 모델 폴더를 찾을 수 없습니다.", status_code=status.HTTP_404_NOT_FOUND)
        subfolder = f"{parent}/{name}" if parent else name
        target = _model_target_directory(payload.model_type, subfolder)
        target.mkdir(exist_ok=False)
        _model_target_directory(payload.model_type, subfolder)
    except CivitaiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="모델 폴더가 이미 있습니다.") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="모델 폴더를 만들 수 없습니다.") from exc
    return ModelFolderResponse(model_type=payload.model_type, subfolder=subfolder)


@router.get("/downloads", response_model=list[ModelDownloadResponse])
def model_downloads(
    user: UserResponse = Depends(current_user),
    limit: int = Query(default=20, ge=1, le=100),
    active_only: bool = False,
) -> list[ModelDownloadResponse]:
    return [_download_response(row) for row in list_model_downloads(user.id, limit, active_only=active_only)]


@router.post("/downloads/{download_id}/retry", response_model=ModelDownloadResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_download(download_id: uuid.UUID, user: UserResponse = Depends(current_user)) -> ModelDownloadResponse:
    row = retry_model_download(download_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="다시 시도할 수 있는 다운로드를 찾을 수 없습니다.")
    return _download_response(row)


@router.post("/downloads/{download_id}/cancel", response_model=ModelDownloadResponse, status_code=status.HTTP_202_ACCEPTED)
def cancel_download(download_id: uuid.UUID, user: UserResponse = Depends(current_user)) -> ModelDownloadResponse:
    row = cancel_model_download(download_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="중단할 수 있는 다운로드를 찾을 수 없습니다.")
    try:
        _partial_path(row["target_path"]).unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="다운로드 임시 파일을 삭제하지 못했습니다.") from exc
    return _download_response(row)


@router.get("/civitai/lookup", response_model=CivitaiLookupResponse)
def lookup_civitai_model(
    source: str = Query(min_length=1, max_length=2048),
    model_type: ModelType = "checkpoint",
    file_index: int | None = Query(default=None, ge=0),
    _: UserResponse = Depends(current_user),
) -> CivitaiLookupResponse:
    try:
        version, target_model_type, selected_index, versions = _resolve_civitai_source(source, model_type, file_index)
    except CivitaiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _lookup_response(version, target_model_type, selected_index, versions)


@router.post("/civitai/download", response_model=ModelDownloadResponse, status_code=status.HTTP_202_ACCEPTED)
def download_civitai_model(
    payload: ModelDownloadRequest,
    user: UserResponse = Depends(current_user),
) -> ModelDownloadResponse:
    if not settings.civitai_token.strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Civitai 토큰이 설정되지 않았습니다.")
    root = Path(settings.comfyui_models_path)
    if not root.is_dir():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ComfyUI 모델 폴더를 찾을 수 없습니다.")
    try:
        version, target_model_type, selected_index, _ = _resolve_civitai_source(payload.source, payload.model_type, payload.file_index)
        selected_file = version.files[selected_index]
        filename = _safe_filename(selected_file.name)
    except CivitaiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    try:
        subfolder = _safe_folder_selection(payload.subfolder)
        target_directory = _model_target_directory(target_model_type, subfolder)
    except CivitaiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if not target_directory.is_dir():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="선택한 모델 폴더를 찾을 수 없습니다.")
    target_path = target_directory / filename
    if target_path.exists() or target_path.is_symlink():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="같은 이름의 모델 파일이 이미 있습니다.")
    row = create_model_download(
        user_id=user.id,
        version_id=version.version_id,
        model_type=target_model_type,
        file_index=selected_index,
        filename=filename,
        target_path=str(target_path),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="같은 모델 다운로드가 이미 대기 중입니다.")
    return _download_response(row)


def _download_response(row: dict[str, Any]) -> ModelDownloadResponse:
    return ModelDownloadResponse(
        id=str(row["id"]),
        version_id=row["version_id"],
        model_type=row["model_type"],
        subfolder=_download_subfolder(row["model_type"], row["target_path"]),
        filename=row["filename"],
        status=row["status"],
        downloaded_bytes=row["downloaded_bytes"],
        total_bytes=row["total_bytes"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


def _safe_subfolder(raw_subfolder: str) -> str:
    value = raw_subfolder.strip()
    if not value:
        return ""
    if len(value) > 255 or "\x00" in value or "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise CivitaiError("저장 하위폴더 경로가 올바르지 않습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    parts = value.split("/")
    if any(
        not part
        or part in {".", ".."}
        or any(ord(char) < 32 for char in part)
        for part in parts
    ):
        raise CivitaiError("저장 하위폴더 경로가 올바르지 않습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return "/".join(parts)


def _safe_folder_selection(raw_subfolder: str) -> str:
    value = _safe_subfolder(raw_subfolder)
    if any(part.startswith(".") for part in Path(value).parts):
        raise CivitaiError("Hidden 모델 폴더는 선택할 수 없습니다.", status.HTTP_400_BAD_REQUEST)
    return value


def _model_target_directory(model_type: ModelType, subfolder: str) -> Path:
    root = Path(settings.comfyui_models_path).resolve()
    base = root / _MODEL_TARGETS[model_type][1]
    try:
        base.resolve().relative_to(root)
        if base.is_symlink():
            raise ValueError("symbolic link")
        target = base
        for part in subfolder.split("/") if subfolder else []:
            target /= part
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise ValueError("unsafe directory")
            target.resolve().relative_to(base.resolve())
        return target
    except (OSError, ValueError) as exc:
        raise CivitaiError("저장 하위폴더 경로가 올바르지 않습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT) from exc


def _download_subfolder(model_type: str, target_path: str) -> str:
    try:
        base = Path(settings.comfyui_models_path).resolve() / _MODEL_TARGETS[cast(ModelType, model_type)][1]
        relative = Path(target_path).relative_to(base)
    except (KeyError, ValueError, TypeError):
        return ""
    return "/".join(relative.parts[:-1])


def _validated_model_target(model_type: ModelType, raw_target_path: str | Path) -> Path:
    target_path = Path(raw_target_path)
    base = _model_target_directory(model_type, "")
    if not target_path.is_absolute():
        raise CivitaiError("모델 저장 경로가 올바르지 않습니다.")
    try:
        relative = target_path.relative_to(base)
        if not relative.parts:
            raise ValueError("missing filename")
        subfolder = _safe_subfolder("/".join(relative.parts[:-1]))
        filename = _safe_filename(relative.parts[-1])
        validated = _model_target_directory(model_type, subfolder) / filename
        if validated != target_path:
            raise ValueError("normalized path differs")
        return validated
    except (CivitaiError, ValueError) as exc:
        raise CivitaiError("모델 저장 경로가 올바르지 않습니다.") from exc


def _lookup_response(
    version: CivitaiVersion,
    target_model_type: ModelType,
    selected_index: int,
    versions: tuple[CivitaiVersion, ...],
) -> CivitaiLookupResponse:
    return CivitaiLookupResponse(
        version_id=version.version_id,
        model_id=version.model_id,
        model_name=version.model_name,
        model_type=version.model_type,
        version_name=version.version_name,
        base_model=version.base_model,
        target_model_type=target_model_type,
        suggested_subfolder=_suggested_subfolder(target_model_type, version.base_model),
        files=[
            CivitaiFileResponse(
                index=index,
                name=file.name,
                file_type=file.file_type,
                size_bytes=file.size_bytes,
                sha256=file.sha256,
                primary=file.primary,
            )
            for index, file in enumerate(version.files)
        ],
        selected_file_index=selected_index,
        versions=[
            CivitaiVersionOption(
                version_id=item.version_id,
                version_name=item.version_name,
                base_model=item.base_model,
                published_at=item.published_at,
            )
            for item in versions
        ],
    )


def _detected_model_type(version: CivitaiVersion) -> ModelType | None:
    version_type = _normalized_label(version.model_type)
    if version_type in {"lora", "locon", "dora"}:
        return "lora"
    if version_type != "checkpoint":
        return None
    base_model = _normalized_label(version.base_model or "")
    return "diffusion_model" if "anima" in base_model or "minimax" in base_model else "checkpoint"


def _suggested_subfolder(model_type: ModelType, base_model: str | None) -> str:
    family = next((name for name in ("anima", "minimax", "illustrious") if name in _normalized_label(base_model or "")), None)
    if family is None:
        return ""
    try:
        directory = _model_target_directory(model_type, "")
        candidates = sorted(
            (path for path in directory.rglob("*") if path.is_dir() and not path.is_symlink()),
            key=lambda path: (len(path.relative_to(directory).parts), str(path.relative_to(directory)).casefold()),
        )
    except (CivitaiError, OSError):
        return ""
    for candidate in candidates:
        relative = candidate.relative_to(directory)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if any(family in _normalized_label(part) for part in relative.parts):
            return _safe_folder_selection("/".join(relative.parts))
    return ""


def _resolve_civitai_source(
    source: str,
    model_type: ModelType,
    file_index: int | None,
) -> tuple[CivitaiVersion, ModelType, int, tuple[CivitaiVersion, ...]]:
    model_id, version_id = _parse_civitai_source(source)
    if model_id is not None:
        versions = _fetch_model_versions(model_id, model_type)
        if version_id is None:
            version = versions[0]
        else:
            version = next((item for item in versions if item.version_id == version_id), None)
            if version is None:
                raise CivitaiError(
                    "선택한 모델 버전에서 해당 모델 타입 파일을 찾지 못했습니다.",
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                )
    else:
        if version_id is None:
            raise CivitaiError("Civitai 모델 버전 ID 또는 링크를 입력해 주세요.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        version = _fetch_version(version_id)
        versions = (version,)
    target_model_type = _detected_model_type(version) or model_type
    return version, target_model_type, _select_file_index(version, target_model_type, file_index), versions


def _parse_civitai_source(source: str) -> tuple[int | None, int | None]:
    value = source.strip()
    if value.isdigit():
        version_id = int(value)
        if version_id < 1:
            raise CivitaiError("올바른 Civitai 모델 버전 ID를 입력해 주세요.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        return None, version_id

    parsed = urlparse(value if "://" in value else f"https://{value}")
    if (parsed.hostname or "").casefold() not in _CIVITAI_SOURCE_HOSTS:
        raise CivitaiError("Civitai 모델 링크를 입력해 주세요.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    query_values = parse_qs(parsed.query).get("modelVersionId", [])
    query_version = query_values[0] if query_values else ""
    if query_values and not query_version.isdigit():
        raise CivitaiError("올바른 Civitai 모델 버전 ID를 입력해 주세요.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    version_match = re.search(r"/(?:model-versions|api/download/models)/(\d+)(?:/|$)", parsed.path)
    model_match = None if version_match else re.search(r"/(?:api/v1/)?models/(\d+)(?:/|$)", parsed.path)
    version_id = int(query_version or (version_match.group(1) if version_match else 0)) or None
    model_id = int(model_match.group(1)) if model_match else None
    if model_id is None and version_id is None:
        raise CivitaiError("Civitai 모델 ID, 버전 ID 또는 링크를 입력해 주세요.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return model_id, version_id


def _parse_version_id(source: str) -> int:
    _, version_id = _parse_civitai_source(source)
    if version_id is None:
        raise CivitaiError("Civitai 모델 버전 ID 또는 링크를 입력해 주세요.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return version_id


def _fetch_version(version_id: int) -> CivitaiVersion:
    return _parse_version(
        _fetch_civitai_payload(f"model-versions/{version_id}", "Civitai 모델 버전을 찾을 수 없습니다."),
        version_id,
    )


def _fetch_model_versions(model_id: int, model_type: ModelType) -> tuple[CivitaiVersion, ...]:
    payload = _fetch_civitai_payload(f"models/{model_id}", "Civitai 모델을 찾을 수 없습니다.")
    raw_versions = payload.get("modelVersions")
    model = {"id": payload.get("id"), "name": payload.get("name"), "type": payload.get("type")}
    versions: list[CivitaiVersion] = []
    for item in raw_versions if isinstance(raw_versions, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        try:
            version = _parse_version({**item, "model": model}, item["id"])
            _select_file_index(version, _detected_model_type(version) or model_type, None)
        except CivitaiError:
            continue
        versions.append(version)
    versions.sort(
        key=lambda item: (item.published_at or datetime.min.replace(tzinfo=timezone.utc), item.version_id),
        reverse=True,
    )
    if not versions:
        label = _MODEL_TARGETS[model_type][0]
        raise CivitaiError(f"이 Civitai 모델에서 다운로드 가능한 {label} 버전을 찾지 못했습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return tuple(versions)


def _fetch_civitai_payload(path: str, not_found_message: str) -> dict[str, Any]:
    request = UrlRequest(
        f"{_CIVITAI_API_BASE}/{path}",
        headers={"Accept": "application/json", "User-Agent": "LocalField/0.1"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except UrlHTTPError as exc:
        if exc.code == 404:
            raise CivitaiError(not_found_message, status.HTTP_404_NOT_FOUND) from exc
        if exc.code in {401, 403}:
            raise CivitaiError("Civitai API 요청 권한이 없습니다.", status.HTTP_502_BAD_GATEWAY) from exc
        raise CivitaiError("Civitai 모델 정보를 조회하지 못했습니다.") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise CivitaiError("Civitai에 연결할 수 없습니다.") from exc
    if not isinstance(payload, dict):
        raise CivitaiError("Civitai 모델 정보 형식이 올바르지 않습니다.")
    return payload


def _parse_version(payload: dict[str, Any], version_id: int) -> CivitaiVersion:
    raw_model = payload.get("model")
    model: dict[str, Any] = raw_model if isinstance(raw_model, dict) else {}
    raw_files_value = payload.get("files")
    raw_files: list[Any] = raw_files_value if isinstance(raw_files_value, list) else []
    files: list[CivitaiFile] = []
    for raw_file in raw_files:
        if not isinstance(raw_file, dict):
            continue
        name = raw_file.get("name")
        download_url = raw_file.get("downloadUrl")
        if not isinstance(name, str) or not isinstance(download_url, str):
            continue
        raw_hashes_value = raw_file.get("hashes")
        raw_hashes: dict[str, Any] = raw_hashes_value if isinstance(raw_hashes_value, dict) else {}
        size_bytes = _size_bytes(raw_file.get("sizeKB"))
        files.append(
            CivitaiFile(
                name=name,
                file_type=str(raw_file.get("type") or "Model"),
                download_url=download_url,
                size_bytes=size_bytes,
                sha256=_string_or_none(raw_hashes.get("SHA256")),
                primary=bool(raw_file.get("primary")),
            )
        )
    if not files:
        raise CivitaiError("다운로드 가능한 Civitai 파일을 찾지 못했습니다.")
    return CivitaiVersion(
        version_id=version_id,
        model_id=int(model["id"]) if isinstance(model.get("id"), int) else None,
        model_name=str(model.get("name") or "알 수 없는 모델"),
        model_type=str(model.get("type") or "Other"),
        version_name=str(payload.get("name") or "알 수 없는 버전"),
        base_model=_string_or_none(payload.get("baseModel")),
        files=tuple(files),
        published_at=_datetime_or_none(payload.get("publishedAt") or payload.get("createdAt")),
    )


def _select_file_index(version: CivitaiVersion, model_type: ModelType, file_index: int | None) -> int:
    if file_index is not None:
        if file_index >= len(version.files):
            raise CivitaiError("선택한 Civitai 파일을 찾을 수 없습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        indexes = [file_index]
    else:
        indexes = [index for index, file in enumerate(version.files) if file.primary]
        indexes.extend(index for index in range(len(version.files)) if index not in indexes)
    for index in indexes:
        if _file_matches(version, version.files[index], model_type):
            return index
    label = _MODEL_TARGETS[model_type][0]
    raise CivitaiError(f"선택한 Civitai 버전에서 {label} 파일을 찾지 못했습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT)


def _file_matches(version: CivitaiVersion, file: CivitaiFile, model_type: ModelType) -> bool:
    if Path(file.name).suffix.casefold() not in _MODEL_EXTENSIONS:
        return False
    version_type = _normalized_label(version.model_type)
    file_type = _normalized_label(file.file_type)
    if model_type in {"checkpoint", "diffusion_model"}:
        return version_type == "checkpoint"
    if model_type == "lora":
        return version_type in {"lora", "locon", "dora"}
    if model_type == "text_encoder":
        return version_type == "textencoder" or file_type == "textencoder" or (
            version_type in {"other", "checkpoint"} and "textencoder" in _normalized_label(file.name)
        )
    if model_type == "vae":
        return version_type == "vae" or file_type == "vae"
    return version_type == "textualinversion"


def _normalized_label(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value.casefold())


def _safe_filename(raw_name: str) -> str:
    candidate = unquote(raw_name.replace("\\", "/").rsplit("/", 1)[-1])
    if any(ord(char) < 32 for char in candidate):
        raise CivitaiError("Civitai 파일 이름이 올바르지 않습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    filename = candidate.strip()
    if not filename or filename in {".", ".."}:
        raise CivitaiError("Civitai 파일 이름이 올바르지 않습니다.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    suffix = Path(filename).suffix.casefold()
    if suffix not in _MODEL_EXTENSIONS:
        raise CivitaiError("ComfyUI에서 지원하지 않는 모델 파일 형식입니다.", status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    if len(filename) > 255:
        filename = f"{Path(filename).stem[:255 - len(suffix)]}{Path(filename).suffix}"
    return filename


def _size_bytes(value: Any) -> int | None:
    try:
        size = int(float(value) * 1024)
    except (TypeError, ValueError):
        return None
    return size if size > 0 else None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _datetime_or_none(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _open_download(url: str, token: str, resume_from: int):
    current_url = url
    for hop in range(_DOWNLOAD_MAX_REDIRECTS + 1):
        parsed = urlparse(current_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise CivitaiError("Civitai 다운로드 주소가 안전하지 않습니다.")
        if hop == 0 and parsed.hostname.casefold() != _CIVITAI_HOST:
            raise CivitaiError("Civitai 다운로드 주소가 올바르지 않습니다.")
        headers = {"User-Agent": "LocalField/0.1"}
        if parsed.hostname.casefold() == _CIVITAI_HOST:
            headers["Authorization"] = f"Bearer {token}"
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
        request = UrlRequest(current_url, headers=headers)
        try:
            return _NO_REDIRECT_OPENER.open(request, timeout=60)
        except UrlHTTPError as exc:
            if exc.code not in _DOWNLOAD_REDIRECT_CODES:
                if exc.code in {401, 403}:
                    raise CivitaiError("Civitai 다운로드 권한이 없습니다.") from exc
                raise CivitaiError("Civitai 파일 다운로드에 실패했습니다.") from exc
            location = exc.headers.get("Location")
            exc.close()
            if not location:
                raise CivitaiError("Civitai 다운로드 경로를 확인할 수 없습니다.") from exc
            current_url = urljoin(current_url, location)
    raise CivitaiError("Civitai 다운로드 리디렉션이 너무 많습니다.")


def _process_model_download(job: dict[str, Any]) -> None:
    if not settings.civitai_token.strip():
        raise CivitaiError("Civitai 토큰이 설정되지 않았습니다.")
    version = _fetch_version(int(job["version_id"]))
    model_type = cast(ModelType, job["model_type"])
    selected_index = _select_file_index(version, model_type, int(job["file_index"]))
    selected_file = version.files[selected_index]
    target = _validated_model_target(model_type, job["target_path"])
    if target.exists() or target.is_symlink():
        raise CivitaiError("같은 이름의 모델 파일이 이미 있습니다.", status.HTTP_409_CONFLICT)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = _partial_path(target)
    try:
        _ensure_model_download_active(job["id"])
        resume_from = partial.stat().st_size if partial.is_file() else 0
        with _open_download(selected_file.download_url, settings.civitai_token.strip(), resume_from) as response:
            _ensure_model_download_active(job["id"])
            response_status = getattr(response, "status", 200)
            append = resume_from > 0 and response_status == 206
            downloaded = resume_from if append else 0
            content_length = _header_int(response, "Content-Length")
            total_bytes = (downloaded + content_length) if append and content_length is not None else content_length
            if total_bytes is None:
                total_bytes = selected_file.size_bytes
            if not update_model_download_progress(job["id"], downloaded, total_bytes):
                raise _ModelDownloadCancelled()
            mode = "ab" if append else "wb"
            last_progress = time.monotonic()
            with partial.open(mode) as destination:
                while True:
                    chunk = response.read(_DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    destination.write(chunk)
                    downloaded += len(chunk)
                    now = time.monotonic()
                    if now - last_progress >= _DOWNLOAD_PROGRESS_INTERVAL:
                        if not update_model_download_progress(job["id"], downloaded, total_bytes):
                            raise _ModelDownloadCancelled()
                        last_progress = now
        _ensure_model_download_active(job["id"])
        actual_bytes = partial.stat().st_size
        if selected_file.sha256:
            digest = hashlib.sha256()
            with partial.open("rb") as source:
                for chunk in iter(lambda: source.read(_DOWNLOAD_CHUNK_BYTES), b""):
                    digest.update(chunk)
            _ensure_model_download_active(job["id"])
            if digest.hexdigest().casefold() != selected_file.sha256.casefold():
                partial.unlink(missing_ok=True)
                raise CivitaiError("다운로드한 모델의 SHA256 검증에 실패했습니다.")
        _ensure_model_download_active(job["id"])
        if target.exists() or target.is_symlink():
            raise CivitaiError("같은 이름의 모델 파일이 이미 있습니다.", status.HTTP_409_CONFLICT)
        os.replace(partial, target)
        if not complete_model_download(job["id"], actual_bytes, total_bytes or actual_bytes):
            target.unlink(missing_ok=True)
            raise _ModelDownloadCancelled()
    except _ModelDownloadCancelled:
        partial.unlink(missing_ok=True)
        raise


def _ensure_model_download_active(download_id: uuid.UUID) -> None:
    if not is_model_download_active(download_id):
        raise _ModelDownloadCancelled()


def _partial_path(target_path: str | Path) -> Path:
    target = Path(target_path)
    return target.with_name(f".{target.name}.part")


def _header_int(response: Any, name: str) -> int | None:
    value = response.headers.get(name)
    try:
        parsed = int(value) if value is not None else None
    except ValueError:
        return None
    return parsed if parsed is not None and parsed >= 0 else None


async def run_model_download_worker(stop_event: asyncio.Event) -> None:
    await asyncio.to_thread(reset_model_downloads)
    while not stop_event.is_set():
        job = await asyncio.to_thread(claim_model_download)
        if job is not None:
            try:
                await asyncio.to_thread(_process_model_download, job)
            except _ModelDownloadCancelled:
                continue
            except CivitaiError as exc:
                await asyncio.to_thread(fail_model_download, job["id"], str(exc))
            except (OSError, URLError, TimeoutError, ValueError):
                await asyncio.to_thread(fail_model_download, job["id"], "Civitai 파일 다운로드에 실패했습니다.")
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
