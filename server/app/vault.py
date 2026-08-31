from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field, model_validator

from .auth import UserResponse, current_user
from .comfyui import _request_bytes
from .database import (
    create_image_edit,
    create_video_edit,
    delete_image_generation,
    delete_image_generations,
    delete_video_generation,
    delete_video_generations,
    get_image_generation_by_id,
    get_image_generations_by_ids,
    get_video_generation_by_id,
    has_generation_storage_reference_outside,
    has_media_asset,
    increment_image_generation_view_count,
    increment_video_generation_view_count,
    list_filtered_image_generations,
    list_filtered_video_generations,
    list_image_generations,
    list_video_generations,
    update_image_favorite,
    update_video_favorite,
)
from .storage import (
    StorageError,
    delete_file as storage_delete_file,
    download_file as storage_download_file,
    enabled as storage_enabled,
    read_url as storage_read_url,
    upload_file as storage_upload_file,
    file_size as storage_file_size,
)
from .media_editing import MediaEditError, edit_video


router = APIRouter(prefix="/vault", tags=["vault"])
VAULT_PAGE_SIZE = 10


class VaultImageSummary(BaseModel):
    id: UUID
    media_type: str
    status: str
    prompt: str
    checkpoint: str
    image_url: str | None
    view_count: int
    is_favorite: bool
    created_at: datetime
    completed_at: datetime | None
    elapsed_seconds: float
    is_edited: bool
    file_size_bytes: int | None


class VaultLora(BaseModel):
    name: str
    strength: float


class VaultImageDetail(VaultImageSummary):
    prompt_id: str
    negative_prompt: str
    loras: list[VaultLora]
    cfg: float
    steps: int
    sampler_name: str
    scheduler: str
    width: int
    height: int
    seed: int
    file_path: str | None
    filename: str | None
    subfolder: str
    image_type: str


class VaultImagePage(BaseModel):
    items: list[VaultImageSummary]
    page: int
    page_size: int
    total_count: int
    completed_count: int
    total_pages: int


class VaultVideoSummary(BaseModel):
    id: UUID
    media_type: str
    mode: str
    fps: float
    status: str
    prompt: str
    video_url: str | None
    view_count: int
    is_favorite: bool
    created_at: datetime
    completed_at: datetime | None
    elapsed_seconds: float
    is_edited: bool
    duration_seconds: float | None
    file_size_bytes: int | None


class VaultVideoPage(BaseModel):
    items: list[VaultVideoSummary]
    page: int
    page_size: int
    total_count: int
    completed_count: int
    total_pages: int


class VaultVideoDetail(VaultVideoSummary):
    width: int
    height: int
    seed: int


class FavoriteRequest(BaseModel):
    is_favorite: bool


class FavoriteResponse(BaseModel):
    is_favorite: bool


class BulkDeleteRequest(BaseModel):
    generation_ids: list[UUID] = Field(min_length=1, max_length=100)


class BulkDeleteResponse(BaseModel):
    deleted_count: int


class ImageEditResponse(BaseModel):
    generation_id: UUID


class VideoEditRequest(BaseModel):
    start_seconds: float = Field(default=0, ge=0, le=600)
    end_seconds: float | None = Field(default=None, gt=0, le=600)
    crop_x: int | None = Field(default=None, ge=0, le=8192)
    crop_y: int | None = Field(default=None, ge=0, le=8192)
    crop_width: int | None = Field(default=None, ge=2, le=8192)
    crop_height: int | None = Field(default=None, ge=2, le=8192)
    rotate: Literal[0, 90, 180, 270] = 0

    @model_validator(mode="after")
    def validate_time_and_crop(self) -> "VideoEditRequest":
        if self.end_seconds is not None and self.end_seconds <= self.start_seconds:
            raise ValueError("종료 시간은 시작 시간보다 커야 합니다.")
        crop_values = (self.crop_x, self.crop_y, self.crop_width, self.crop_height)
        if any(value is not None for value in crop_values) and not all(value is not None for value in crop_values):
            raise ValueError("crop 영역은 x, y, width, height를 모두 입력해야 합니다.")
        return self


class VideoEditResponse(BaseModel):
    generation_id: UUID


@router.get("/videos", response_model=VaultVideoPage)
def vault_videos(
    search: str = Query(default="", max_length=500),
    sort: Literal["latest", "oldest", "most_viewed"] = "latest",
    favorites_only: bool = False,
    page: int = Query(default=1, ge=1),
    user: UserResponse = Depends(current_user),
) -> VaultVideoPage:
    rows, total_count, completed_count = list_video_generations(
        user.id,
        search=search,
        sort=sort,
        favorites_only=favorites_only,
        page=page,
    )
    return VaultVideoPage(
        items=[_video_summary(row, user.id) for row in rows],
        page=page,
        page_size=VAULT_PAGE_SIZE,
        total_count=total_count,
        completed_count=completed_count,
        total_pages=(total_count + VAULT_PAGE_SIZE - 1) // VAULT_PAGE_SIZE,
    )


@router.get("/images", response_model=VaultImagePage)
def vault_images(
    search: str = Query(default="", max_length=500),
    sort: Literal["latest", "oldest", "most_viewed"] = "latest",
    favorites_only: bool = False,
    page: int = Query(default=1, ge=1),
    user: UserResponse = Depends(current_user),
) -> VaultImagePage:
    rows, total_count, completed_count = list_image_generations(
        user.id,
        search=search,
        sort=sort,
        favorites_only=favorites_only,
        page=page,
    )
    return VaultImagePage(
        items=[_summary(row, user.id) for row in rows],
        page=page,
        page_size=VAULT_PAGE_SIZE,
        total_count=total_count,
        completed_count=completed_count,
        total_pages=(total_count + VAULT_PAGE_SIZE - 1) // VAULT_PAGE_SIZE,
    )


@router.delete("/videos/filtered", response_model=BulkDeleteResponse)
def delete_filtered_vault_videos(
    search: str = Query(default="", max_length=500),
    favorites_only: bool = False,
    expected_count: int = Query(ge=0),
    confirmed: bool = False,
    user: UserResponse = Depends(current_user),
) -> BulkDeleteResponse:
    generations = list_filtered_video_generations(user.id, search=search, favorites_only=favorites_only)
    _validate_filtered_delete(len(generations), expected_count, confirmed)
    generation_ids = [generation["id"] for generation in generations]
    return BulkDeleteResponse(
        deleted_count=_delete_generation_rows(generations, generation_ids, delete_video_generations, user)
    )


@router.delete("/images/filtered", response_model=BulkDeleteResponse)
def delete_filtered_vault_images(
    search: str = Query(default="", max_length=500),
    favorites_only: bool = False,
    expected_count: int = Query(ge=0),
    confirmed: bool = False,
    user: UserResponse = Depends(current_user),
) -> BulkDeleteResponse:
    generations = list_filtered_image_generations(user.id, search=search, favorites_only=favorites_only)
    _validate_filtered_delete(len(generations), expected_count, confirmed)
    generation_ids = [generation["id"] for generation in generations]
    return BulkDeleteResponse(
        deleted_count=_delete_generation_rows(generations, generation_ids, delete_image_generations, user)
    )


@router.post("/videos/{generation_id}/edit", response_model=VideoEditResponse, status_code=status.HTTP_201_CREATED)
def edit_vault_video(
    generation_id: UUID,
    payload: VideoEditRequest,
    user: UserResponse = Depends(current_user),
) -> VideoEditResponse:
    generation = get_video_generation_by_id(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상 결과를 찾을 수 없습니다.")
    if generation["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="완료된 영상만 편집할 수 있습니다.")
    storage_file_id = generation.get("storage_file_id")
    if not storage_enabled() or not isinstance(storage_file_id, str) or not storage_file_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="영상 Storage 파일을 사용할 수 없습니다.")
    try:
        content, _ = storage_download_file(file_id=storage_file_id, owner_id=str(user.id))
        started_at = monotonic()
        edited = edit_video(
            content=content,
            filename=generation.get("filename") or "video.mp4",
            start_seconds=payload.start_seconds,
            end_seconds=payload.end_seconds,
            crop_x=payload.crop_x,
            crop_y=payload.crop_y,
            crop_width=payload.crop_width,
            crop_height=payload.crop_height,
            rotate=payload.rotate,
        )
        edit_elapsed = round(monotonic() - started_at, 3)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except MediaEditError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        edited_file_id = storage_upload_file(
            content=edited.content,
            media_type="video/mp4",
            owner_id=str(user.id),
        )
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    try:
        edited_id = create_video_edit(
            user_id=user.id,
            source_generation_id=generation_id,
            storage_file_id=edited_file_id,
            filename=edited.filename,
            width=edited.width,
            height=edited.height,
            length=edited.frame_count,
            elapsed_seconds=edit_elapsed,
            size_bytes=len(edited.content),
        )
    except Exception as exc:
        try:
            storage_delete_file(file_id=edited_file_id, owner_id=str(user.id))
        except StorageError:
            pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="편집한 영상을 저장하지 못했습니다.") from exc
    if edited_id is None:
        try:
            storage_delete_file(file_id=edited_file_id, owner_id=str(user.id))
        except StorageError:
            pass
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상 결과를 찾을 수 없습니다.")
    return VideoEditResponse(generation_id=edited_id)


@router.get("/videos/{generation_id}", response_model=VaultVideoDetail)
def vault_video_detail(
    generation_id: UUID,
    user: UserResponse = Depends(current_user),
) -> VaultVideoDetail:
    generation = increment_video_generation_view_count(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상 콘텐츠를 찾을 수 없습니다.")
    return VaultVideoDetail(
        **_video_summary(generation, user.id, include_file_size=True).model_dump(),
        width=generation["width"],
        height=generation["height"],
        seed=generation["seed"],
    )


@router.patch("/videos/{generation_id}/favorite", response_model=FavoriteResponse)
def update_vault_video_favorite(
    generation_id: UUID,
    payload: FavoriteRequest,
    user: UserResponse = Depends(current_user),
) -> FavoriteResponse:
    is_favorite = update_video_favorite(generation_id, user.id, payload.is_favorite)
    if is_favorite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상 콘텐츠를 찾을 수 없습니다.")
    return FavoriteResponse(is_favorite=is_favorite)


@router.delete("/videos/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault_video(
    generation_id: UUID,
    user: UserResponse = Depends(current_user),
) -> Response:
    generation = get_video_generation_by_id(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상 콘텐츠를 찾을 수 없습니다.")
    storage_file_id = generation.get("storage_file_id")
    if storage_file_id and not has_media_asset(storage_file_id, user.id):
        if not storage_enabled():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
        try:
            storage_delete_file(file_id=storage_file_id, owner_id=str(user.id))
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if not delete_video_generation(generation_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상 콘텐츠를 찾을 수 없습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/images/bulk", response_model=BulkDeleteResponse)
def delete_vault_images(
    payload: BulkDeleteRequest,
    user: UserResponse = Depends(current_user),
) -> BulkDeleteResponse:
    generations = get_image_generations_by_ids(payload.generation_ids, user.id)
    if len(generations) != len(payload.generation_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 콘텐츠를 찾을 수 없습니다.")
    deleted_count = _delete_generation_rows(generations, payload.generation_ids, delete_image_generations, user)
    if deleted_count != len(payload.generation_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 콘텐츠를 찾을 수 없습니다.")
    return BulkDeleteResponse(deleted_count=deleted_count)


def _delete_generation_rows(
    generations: list[dict],
    generation_ids: list[UUID],
    delete_records: Callable[[list[UUID], UUID], int],
    user: UserResponse,
) -> int:
    if not generation_ids:
        return 0
    storage_file_ids = list(
        dict.fromkeys(
            generation["storage_file_id"]
            for generation in generations
            if isinstance(generation.get("storage_file_id"), str)
            and generation["storage_file_id"]
            and not has_media_asset(generation["storage_file_id"], user.id)
            and not has_generation_storage_reference_outside(
                generation["storage_file_id"], user.id, generation_ids
            )
        )
    )
    if storage_file_ids and not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    try:
        if storage_file_ids:
            with ThreadPoolExecutor(max_workers=min(len(storage_file_ids), 8)) as executor:
                storage_futures = [
                    executor.submit(storage_delete_file, file_id=file_id, owner_id=str(user.id))
                    for file_id in storage_file_ids
                ]
                for future in storage_futures:
                    future.result()
        deleted_count = delete_records(generation_ids, user.id)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return deleted_count


def _validate_filtered_delete(actual_count: int, expected_count: int, confirmed: bool) -> None:
    if not confirmed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="전체 삭제 확인이 필요합니다.")
    if actual_count != expected_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="필터 결과가 변경되었습니다. 목록을 새로고침한 뒤 다시 확인해 주세요.",
        )


@router.get("/images/{generation_id}/source")
def vault_image_source(
    generation_id: UUID,
    user: UserResponse = Depends(current_user),
) -> Response:
    generation = get_image_generation_by_id(generation_id, user.id)
    if generation is None or generation["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이미지 결과를 찾을 수 없습니다.")
    storage_file_id = generation.get("storage_file_id")
    try:
        if storage_enabled() and isinstance(storage_file_id, str) and storage_file_id:
            content, media_type = storage_download_file(file_id=storage_file_id, owner_id=str(user.id))
        else:
            filename = generation.get("filename")
            if not isinstance(filename, str) or not filename:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이미지 결과를 찾을 수 없습니다.")
            query = urlencode(
                {
                    "filename": filename,
                    "subfolder": generation.get("subfolder", ""),
                    "type": generation.get("image_type", "output"),
                }
            )
            content, media_type = _request_bytes(f"/view?{query}")
    except HTTPException:
        raise
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="이미지 원본을 읽을 수 없습니다.") from exc
    return Response(content=content, media_type=media_type or "image/png")


@router.post("/images/{generation_id}/edit", response_model=ImageEditResponse, status_code=status.HTTP_201_CREATED)
def edit_vault_image(
    generation_id: UUID,
    file: UploadFile = File(...),
    width: int = Form(..., ge=1, le=8192),
    height: int = Form(..., ge=1, le=8192),
    user: UserResponse = Depends(current_user),
) -> ImageEditResponse:
    generation = get_image_generation_by_id(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이미지 결과를 찾을 수 없습니다.")
    if generation["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="완료된 이미지만 편집할 수 있습니다.")
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="이미지 파일만 저장할 수 있습니다.")
    content = file.file.read(50 * 1024 * 1024 + 1)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="편집할 이미지 파일이 너무 큽니다.")
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="빈 이미지 파일은 저장할 수 없습니다.")
    filename = Path(file.filename or "edited.png").name or "edited.png"
    try:
        storage_file_id = storage_upload_file(content=content, media_type=content_type, owner_id=str(user.id))
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    try:
        edited_id = create_image_edit(
            user_id=user.id,
            source_generation_id=generation_id,
            storage_file_id=storage_file_id,
            filename=filename[:255],
            width=width,
            height=height,
            elapsed_seconds=0,
            size_bytes=len(content),
        )
    except Exception as exc:
        try:
            storage_delete_file(file_id=storage_file_id, owner_id=str(user.id))
        except StorageError:
            pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="편집한 이미지를 저장하지 못했습니다.") from exc
    if edited_id is None:
        try:
            storage_delete_file(file_id=storage_file_id, owner_id=str(user.id))
        except StorageError:
            pass
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이미지 결과를 찾을 수 없습니다.")
    return ImageEditResponse(generation_id=edited_id)


@router.get("/images/{generation_id}", response_model=VaultImageDetail)
def vault_image_detail(
    generation_id: UUID,
    user: UserResponse = Depends(current_user),
) -> VaultImageDetail:
    generation = increment_image_generation_view_count(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="생성 결과를 찾을 수 없습니다.")
    return _detail(generation, user.id)


@router.patch("/images/{generation_id}/favorite", response_model=FavoriteResponse)
def update_vault_image_favorite(
    generation_id: UUID,
    payload: FavoriteRequest,
    user: UserResponse = Depends(current_user),
) -> FavoriteResponse:
    is_favorite = update_image_favorite(generation_id, user.id, payload.is_favorite)
    if is_favorite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="생성 결과를 찾을 수 없습니다.")
    return FavoriteResponse(is_favorite=is_favorite)


@router.delete("/images/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault_image(
    generation_id: UUID,
    user: UserResponse = Depends(current_user),
) -> Response:
    generation = get_image_generation_by_id(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="생성 결과를 찾을 수 없습니다.")

    storage_file_id = generation.get("storage_file_id")
    if storage_file_id and not has_media_asset(storage_file_id, user.id):
        if not storage_enabled():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
        try:
            storage_delete_file(file_id=storage_file_id, owner_id=str(user.id))
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not delete_image_generation(generation_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="생성 결과를 찾을 수 없습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _video_summary(generation: dict, user_id: UUID, *, include_file_size: bool = False) -> VaultVideoSummary:
    video_url = None
    storage_file_id = generation.get("storage_file_id")
    if storage_enabled() and isinstance(storage_file_id, str) and storage_file_id:
        try:
            video_url = storage_read_url(file_id=storage_file_id, owner_id=str(user_id))
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return VaultVideoSummary(
        id=generation["id"],
        media_type="video",
        mode=generation["mode"],
        fps=generation["fps"],
        status=generation["status"],
        prompt=generation["prompt"],
        video_url=video_url,
        view_count=generation["view_count"],
        is_favorite=generation["is_favorite"],
        created_at=generation["created_at"],
        completed_at=generation["completed_at"],
        elapsed_seconds=generation["elapsed_seconds"],
        is_edited=generation["is_edited"],
        duration_seconds=(float(generation["length"]) / float(generation["fps"])) if generation.get("fps") else None,
        file_size_bytes=_generation_file_size(generation, user_id, include_file_size),
    )


def _summary(generation: dict, user_id: UUID, *, include_file_size: bool = False) -> VaultImageSummary:
    return VaultImageSummary(
        id=generation["id"],
        media_type="image",
        status=generation["status"],
        prompt=generation["prompt"],
        checkpoint=generation["checkpoint"],
        image_url=_image_url(generation, user_id),
        view_count=generation["view_count"],
        is_favorite=generation["is_favorite"],
        created_at=generation["created_at"],
        completed_at=generation["completed_at"],
        elapsed_seconds=generation["elapsed_seconds"],
        is_edited=generation["is_edited"],
        file_size_bytes=_generation_file_size(generation, user_id, include_file_size),
    )


def _detail(generation: dict, user_id: UUID) -> VaultImageDetail:
    return VaultImageDetail(
        **_summary(generation, user_id, include_file_size=True).model_dump(),
        prompt_id=generation["prompt_id"],
        negative_prompt=generation["negative_prompt"],
        loras=_loras(generation),
        cfg=generation["cfg"],
        steps=generation["steps"],
        sampler_name=generation["sampler_name"],
        scheduler=generation["scheduler"],
        width=generation["width"],
        height=generation["height"],
        seed=generation["seed"],
        file_path=generation["file_path"],
        filename=generation["filename"],
        subfolder=generation["subfolder"],
        image_type=generation["image_type"],
    )


def _generation_file_size(generation: dict, user_id: UUID, include_storage_lookup: bool) -> int | None:
    stored_size = int(generation.get("size_bytes") or 0)
    if stored_size > 0 or not include_storage_lookup:
        return stored_size or None
    storage_file_id = generation.get("storage_file_id")
    if not storage_enabled() or not isinstance(storage_file_id, str) or not storage_file_id:
        return None
    try:
        return storage_file_size(file_id=storage_file_id, owner_id=str(user_id))
    except StorageError:
        return None


def _loras(generation: dict) -> list[VaultLora]:
    stored = generation.get("loras")
    if isinstance(stored, list):
        return [VaultLora.model_validate(lora) for lora in stored]
    return []


def _image_url(generation: dict, user_id: UUID) -> str | None:
    storage_file_id = generation.get("storage_file_id")
    if storage_enabled() and isinstance(storage_file_id, str) and storage_file_id:
        try:
            return storage_read_url(file_id=storage_file_id, owner_id=str(user_id))
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if not generation["filename"]:
        return None
    query = urlencode(
        {
            "filename": generation["filename"],
            "subfolder": generation["subfolder"],
            "type": generation["image_type"],
        }
    )
    return f"/generation/image/{generation['prompt_id']}/view?{query}"
