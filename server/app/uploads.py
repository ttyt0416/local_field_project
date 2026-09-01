from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .database import create_media_asset, delete_media_asset, get_media_asset, list_reusable_media
from .media_editing import MediaEditError, edit_video, probe_video
from .storage import (
    StorageError,
    delete_file as storage_delete_file,
    download_file as storage_download_file,
    enabled as storage_enabled,
    read_url as storage_read_url,
    upload_file as storage_upload_file,
)
from .vault import VideoEditRequest


router = APIRouter(prefix="/uploads", tags=["media library"])
UPLOADS_PAGE_SIZE = 10
_MAX_IMAGE_BYTES = 50 * 1024 * 1024
ImageGenerationMode = Literal["t2i", "i2i"]
ImageModelFamily = Literal["anima", "illustrious", "krea2"]


class MediaAssetResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    media_kind: Literal["image", "audio", "video"]
    source_type: str
    url: str | None
    created_at: datetime
    size: int


class MediaAssetDetailResponse(MediaAssetResponse):
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None


class MediaAssetPage(BaseModel):
    items: list[MediaAssetResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int


class UploadEditResponse(BaseModel):
    generation_id: str


@router.get("/{file_id}", response_model=MediaAssetDetailResponse)
def upload_detail(
    file_id: str,
    user: UserResponse = Depends(current_user),
) -> MediaAssetDetailResponse:
    asset = _owned_asset(file_id, user)
    url = _read_url(file_id, user)
    duration_seconds = None
    width = None
    height = None
    if asset["media_kind"] == "video":
        try:
            content, _ = storage_download_file(file_id=file_id, owner_id=str(user.id))
            metadata = probe_video(content=content, filename=asset["filename"])
            duration_seconds = metadata.duration
            width = metadata.width
            height = metadata.height
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except MediaEditError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return MediaAssetDetailResponse(
        file_id=asset["storage_file_id"],
        filename=asset["filename"],
        content_type=asset["content_type"],
        media_kind=asset["media_kind"],
        source_type=asset["source_type"],
        url=url,
        created_at=asset["created_at"],
        size=int(asset["size"]),
        duration_seconds=duration_seconds,
        width=width,
        height=height,
    )


@router.get("/{file_id}/source")
def upload_source(
    file_id: str,
    user: UserResponse = Depends(current_user),
) -> Response:
    asset = _owned_asset(file_id, user)
    try:
        content, media_type = storage_download_file(file_id=file_id, owner_id=str(user.id))
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return Response(content=content, media_type=media_type or asset["content_type"])


@router.post("/{file_id}/edit", response_model=UploadEditResponse, status_code=status.HTTP_201_CREATED)
def edit_uploaded_image(
    file_id: str,
    file: UploadFile = File(...),
    width: int = Form(..., ge=1, le=8192),
    height: int = Form(..., ge=1, le=8192),
    user: UserResponse = Depends(current_user),
) -> UploadEditResponse:
    asset = _owned_asset(file_id, user)
    if asset["media_kind"] != "image":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="이미지 콘텐츠만 편집할 수 있습니다.")
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="이미지 파일만 저장할 수 있습니다.")
    content = file.file.read(_MAX_IMAGE_BYTES + 1)
    if len(content) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="편집할 이미지 파일이 너무 큽니다.")
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="빈 이미지 파일은 저장할 수 없습니다.")
    filename = f"{Path(asset['filename']).stem or 'image'}-edited.png"[:255]
    edited_file_id = ""
    try:
        edited_file_id = storage_upload_file(content=content, media_type="image/png", owner_id=str(user.id))
        created = create_media_asset(
            user_id=user.id,
            storage_file_id=edited_file_id,
            filename=filename,
            content_type="image/png",
            media_kind="image",
            size=len(content),
            source_type="edited_upload",
        )
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        _remove_storage_file(edited_file_id, user)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="편집한 이미지를 저장하지 못했습니다.") from exc
    if created is None:
        _remove_storage_file(edited_file_id, user)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="편집한 이미지를 저장하지 못했습니다.")
    return UploadEditResponse(generation_id=edited_file_id)


@router.post("/{file_id}/edit/video", response_model=UploadEditResponse, status_code=status.HTTP_201_CREATED)
def edit_uploaded_video(
    file_id: str,
    payload: VideoEditRequest,
    user: UserResponse = Depends(current_user),
) -> UploadEditResponse:
    asset = _owned_asset(file_id, user)
    if asset["media_kind"] != "video":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="동영상 콘텐츠만 편집할 수 있습니다.")
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    edited_file_id = ""
    try:
        content, _ = storage_download_file(file_id=file_id, owner_id=str(user.id))
        edited = edit_video(
            content=content,
            filename=asset["filename"],
            start_seconds=payload.start_seconds,
            end_seconds=payload.end_seconds,
            crop_x=payload.crop_x,
            crop_y=payload.crop_y,
            crop_width=payload.crop_width,
            crop_height=payload.crop_height,
            rotate=payload.rotate,
        )
        edited_file_id = storage_upload_file(content=edited.content, media_type="video/mp4", owner_id=str(user.id))
        created = create_media_asset(
            user_id=user.id,
            storage_file_id=edited_file_id,
            filename=edited.filename,
            content_type="video/mp4",
            media_kind="video",
            size=len(edited.content),
            source_type="edited_upload",
        )
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except MediaEditError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        if "edited_file_id" in locals():
            _remove_storage_file(edited_file_id, user)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="편집한 영상을 저장하지 못했습니다.") from exc
    if created is None:
        _remove_storage_file(edited_file_id, user)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="편집한 영상을 저장하지 못했습니다.")
    return UploadEditResponse(generation_id=edited_file_id)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    file_id: str,
    user: UserResponse = Depends(current_user),
) -> Response:
    _owned_asset(file_id, user)
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    try:
        storage_delete_file(file_id=file_id, owner_id=str(user.id))
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if not delete_media_asset(file_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업로드 콘텐츠를 찾을 수 없습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=MediaAssetPage)
def reusable_media(
    search: str = Query(default="", max_length=200),
    sort: Literal["latest", "oldest", "name"] = "latest",
    include_generated: bool = False,
    media_kind: Literal["image", "audio", "video"] | None = None,
    page: int = Query(default=1, ge=1),
    user: UserResponse = Depends(current_user),
    source: Literal["uploaded", "generated"] | None = None,
    generation_mode: ImageGenerationMode | None = None,
    model_family: ImageModelFamily | None = None,
) -> MediaAssetPage:
    if (generation_mode is None) != (model_family is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="생성 이미지 분류를 모두 선택해 주세요.")
    if generation_mode is not None and (source != "generated" or media_kind != "image"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="생성 이미지 분류는 생성 이미지에만 사용할 수 있습니다.")
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    result: list[MediaAssetResponse] = []
    media_filters = {
        "search": search,
        "sort": sort,
        "include_generated": include_generated,
        "media_kind": media_kind,
        "page": page,
    }
    if source is not None:
        media_filters["source_type"] = source
    if generation_mode is not None:
        media_filters["generation_mode"] = generation_mode
        media_filters["model_family"] = model_family
    assets, total_count = list_reusable_media(user.id, **media_filters)
    for asset in assets:
        url = None
        try:
            url = storage_read_url(file_id=asset["file_id"], owner_id=str(user.id))
        except StorageError:
            # A stale object remains visible without a preview until it is repaired or removed.
            pass
        result.append(MediaAssetResponse(**asset, url=url))
    return MediaAssetPage(
        items=result,
        page=page,
        page_size=UPLOADS_PAGE_SIZE,
        total_count=total_count,
        total_pages=(total_count + UPLOADS_PAGE_SIZE - 1) // UPLOADS_PAGE_SIZE,
    )


def _owned_asset(file_id: str, user: UserResponse) -> dict:
    asset = get_media_asset(file_id, user.id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업로드 콘텐츠를 찾을 수 없습니다.")
    return asset


def _read_url(file_id: str, user: UserResponse) -> str:
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    try:
        return storage_read_url(file_id=file_id, owner_id=str(user.id))
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def _remove_storage_file(file_id: str, user: UserResponse) -> None:
    try:
        storage_delete_file(file_id=file_id, owner_id=str(user.id))
    except StorageError:
        pass
