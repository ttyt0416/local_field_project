from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import UserResponse, current_user
from .database import create_preset, delete_preset, list_presets, update_preset


router = APIRouter(prefix="/presets", tags=["presets"])
PresetType = Literal["t2i", "video"]
PresetAspectRatio = Literal["custom", "2:3", "3:2", "1:1", "16:9", "9:16"]
PresetVideoMode = Literal["i2v", "fl2v", "r2v"]


class PresetLora(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    strength: float


class PresetValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str | None = Field(default=None, min_length=1, max_length=5000)
    negative_prompt: str | None = Field(default=None, min_length=1, max_length=5000)
    prompt_enhancement_enabled: bool | None = None
    improved_prompt: str | None = Field(default=None, min_length=1, max_length=5000)
    checkpoint: str | None = Field(default=None, min_length=1, max_length=255)
    loras: list[PresetLora] | None = Field(default=None, max_length=8)
    aspect_ratio: PresetAspectRatio | None = None
    width: int | None = Field(default=None, ge=32, le=2048)
    height: int | None = Field(default=None, ge=32, le=2048)
    cfg: float | None = Field(default=None, ge=0, le=20)
    steps: int | None = Field(default=None, ge=1, le=100)
    sampler_name: str | None = Field(default=None, min_length=1, max_length=64)
    scheduler: str | None = Field(default=None, min_length=1, max_length=64)
    mode: PresetVideoMode | None = None
    duration: float | None = None
    fps: float | None = Field(default=None, ge=1, le=120)
    seed: str | None = Field(default=None, min_length=1, max_length=19, pattern=r"^[0-9]+$")
    random_seed: bool | None = None


class PresetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: PresetType
    name: str = Field(min_length=1, max_length=100)
    values: PresetValues
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("프리셋 이름을 입력해 주세요.")
        return normalized


class PresetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: PresetType = "t2i"
    name: str = Field(min_length=1, max_length=100)
    values: PresetValues
    is_default: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("프리셋 이름을 입력해 주세요.")
        return normalized


class PresetResponse(BaseModel):
    id: UUID
    type: str
    name: str
    values: dict[str, Any]
    is_default: bool
    saved_fields: list[str]
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[PresetResponse])
def get_presets(
    preset_type: PresetType = Query(default="t2i", alias="type"),
    user: UserResponse = Depends(current_user),
) -> list[PresetResponse]:
    return [_response(row) for row in list_presets(user_id=user.id, preset_type=preset_type)]


@router.post("", response_model=PresetResponse, status_code=status.HTTP_201_CREATED)
def save_preset(
    payload: PresetCreateRequest,
    user: UserResponse = Depends(current_user),
) -> PresetResponse:
    values = payload.values.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=422, detail="저장할 설정을 하나 이상 선택해 주세요.")
    return _response(
        create_preset(
            user_id=user.id,
            preset_type=payload.type,
            name=payload.name,
            values=values,
            is_default=payload.is_default,
        )
    )


@router.put("/{preset_id}", response_model=PresetResponse)
def edit_preset(
    preset_id: UUID,
    payload: PresetUpdateRequest,
    user: UserResponse = Depends(current_user),
) -> PresetResponse:
    values = payload.values.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=422, detail="저장할 설정을 하나 이상 선택해 주세요.")
    row = update_preset(
        preset_id=preset_id,
        user_id=user.id,
        preset_type=payload.type,
        name=payload.name,
        values=values,
        is_default=payload.is_default,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프리셋을 찾을 수 없습니다.")
    return _response(row)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_preset(
    preset_id: UUID,
    preset_type: PresetType = Query(default="t2i", alias="type"),
    user: UserResponse = Depends(current_user),
) -> Response:
    if not delete_preset(preset_id=preset_id, user_id=user.id, preset_type=preset_type):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프리셋을 찾을 수 없습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _response(row: dict[str, Any]) -> PresetResponse:
    values = row["values"] if isinstance(row["values"], dict) else {}
    return PresetResponse(
        id=row["id"],
        type=row["type"],
        name=row["name"],
        values=values,
        is_default=row["is_default"],
        saved_fields=list(values),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
