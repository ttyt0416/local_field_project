from datetime import datetime
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .database import get_image_generation_by_id, list_image_generations
from .storage import StorageError, enabled as storage_enabled, read_url as storage_read_url


router = APIRouter(prefix="/vault", tags=["vault"])


class VaultImageSummary(BaseModel):
    id: UUID
    media_type: str
    status: str
    prompt: str
    checkpoint: str
    image_url: str | None
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


@router.get("/images", response_model=list[VaultImageSummary])
def vault_images(user: UserResponse = Depends(current_user)) -> list[VaultImageSummary]:
    return [_summary(row, user.id) for row in list_image_generations(user.id)]


@router.get("/images/{generation_id}", response_model=VaultImageDetail)
def vault_image_detail(
    generation_id: UUID,
    user: UserResponse = Depends(current_user),
) -> VaultImageDetail:
    generation = get_image_generation_by_id(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="생성 결과를 찾을 수 없습니다.")
    return _detail(generation, user.id)


def _summary(generation: dict, user_id: UUID) -> VaultImageSummary:
    return VaultImageSummary(
        id=generation["id"],
        media_type="image",
        status=generation["status"],
        prompt=generation["prompt"],
        checkpoint=generation["checkpoint"],
        image_url=_image_url(generation, user_id),
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
