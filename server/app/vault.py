from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from .auth import UserResponse, current_user
from .database import (
    delete_image_generation,
    delete_image_generations,
    get_image_generation_by_id,
    get_image_generations_by_ids,
    increment_image_generation_view_count,
    list_image_generations,
    update_image_favorite,
)
from .storage import StorageError, delete_file as storage_delete_file, enabled as storage_enabled, read_url as storage_read_url


router = APIRouter(prefix="/vault", tags=["vault"])


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


class VaultLora(BaseModel):
    name: str
    strength: float


class VaultImageDetail(VaultImageSummary):
    prompt_id: str
    negative_prompt: str
    loras: list[VaultLora]
    cfg: float
    steps: int
    width: int
    height: int
    seed: int
    file_path: str | None
    filename: str | None
    subfolder: str
    image_type: str


class FavoriteRequest(BaseModel):
    is_favorite: bool


class FavoriteResponse(BaseModel):
    is_favorite: bool


class BulkDeleteRequest(BaseModel):
    generation_ids: list[UUID] = Field(min_length=1, max_length=100)


class BulkDeleteResponse(BaseModel):
    deleted_count: int


@router.get("/images", response_model=list[VaultImageSummary])
def vault_images(
    search: str = Query(default="", max_length=500),
    sort: Literal["latest", "oldest", "most_viewed"] = "latest",
    favorites_only: bool = False,
    user: UserResponse = Depends(current_user),
) -> list[VaultImageSummary]:
    return [
        _summary(row, user.id)
        for row in list_image_generations(
            user.id,
            search=search,
            sort=sort,
            favorites_only=favorites_only,
        )
    ]


@router.delete("/images/bulk", response_model=BulkDeleteResponse)
def delete_vault_images(
    payload: BulkDeleteRequest,
    user: UserResponse = Depends(current_user),
) -> BulkDeleteResponse:
    generations = get_image_generations_by_ids(payload.generation_ids, user.id)
    if len(generations) != len(payload.generation_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 콘텐츠를 찾을 수 없습니다.")

    storage_file_ids = list(
        dict.fromkeys(
            generation["storage_file_id"]
            for generation in generations
            if isinstance(generation.get("storage_file_id"), str) and generation["storage_file_id"]
        )
    )
    if storage_file_ids and not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    try:
        if storage_file_ids:
            with ThreadPoolExecutor(max_workers=min(len(storage_file_ids) + 1, 8)) as executor:
                database_future = executor.submit(delete_image_generations, payload.generation_ids, user.id)
                storage_futures = [
                    executor.submit(storage_delete_file, file_id=file_id, owner_id=str(user.id))
                    for file_id in storage_file_ids
                ]
                deleted_count = database_future.result()
                for future in storage_futures:
                    future.result()
        else:
            deleted_count = delete_image_generations(payload.generation_ids, user.id)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if deleted_count != len(payload.generation_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 콘텐츠를 찾을 수 없습니다.")
    return BulkDeleteResponse(deleted_count=deleted_count)


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
    if storage_file_id:
        if not storage_enabled():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
        try:
            storage_delete_file(file_id=storage_file_id, owner_id=str(user.id))
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not delete_image_generation(generation_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="생성 결과를 찾을 수 없습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _summary(generation: dict, user_id: UUID) -> VaultImageSummary:
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
    )


def _detail(generation: dict, user_id: UUID) -> VaultImageDetail:
    return VaultImageDetail(
        **_summary(generation, user_id).model_dump(),
        prompt_id=generation["prompt_id"],
        negative_prompt=generation["negative_prompt"],
        loras=_loras(generation),
        cfg=generation["cfg"],
        steps=generation["steps"],
        width=generation["width"],
        height=generation["height"],
        seed=generation["seed"],
        file_path=generation["file_path"],
        filename=generation["filename"],
        subfolder=generation["subfolder"],
        image_type=generation["image_type"],
    )


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
