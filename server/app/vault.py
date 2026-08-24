from datetime import datetime
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .database import get_image_generation_by_id, list_image_generations


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


class VaultImageDetail(VaultImageSummary):
    prompt_id: str
    negative_prompt: str
    lora: str | None
    lora_strength: float
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
    return [_summary(row) for row in list_image_generations(user.id)]


@router.get("/images/{generation_id}", response_model=VaultImageDetail)
def vault_image_detail(
    generation_id: UUID,
    user: UserResponse = Depends(current_user),
) -> VaultImageDetail:
    generation = get_image_generation_by_id(generation_id, user.id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="생성 결과를 찾을 수 없습니다.")
    return _detail(generation)


def _summary(generation: dict) -> VaultImageSummary:
    return VaultImageSummary(
        id=generation["id"],
        media_type="image",
        status=generation["status"],
        prompt=generation["prompt"],
        checkpoint=generation["checkpoint"],
        image_url=_image_url(generation),
        created_at=generation["created_at"],
        completed_at=generation["completed_at"],
    )


def _detail(generation: dict) -> VaultImageDetail:
    return VaultImageDetail(
        **_summary(generation).model_dump(),
        prompt_id=generation["prompt_id"],
        negative_prompt=generation["negative_prompt"],
        lora=generation["lora"],
        lora_strength=generation["lora_strength"],
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


def _image_url(generation: dict) -> str | None:
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
