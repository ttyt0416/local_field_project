from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .database import list_active_image_generations, list_active_video_generations


router = APIRouter(prefix="/generation", tags=["generation"])
GenerationKind = Literal["image", "video"]
GenerationStatus = Literal["queued", "processing"]
VideoMode = Literal["i2v", "fl2v", "r2v"]


class ActiveGeneration(BaseModel):
    kind: GenerationKind
    prompt_id: str
    client_id: str
    generation_id: str
    mode: VideoMode | None = None
    status: GenerationStatus
    created_at: datetime


@router.get("/active", response_model=list[ActiveGeneration])
def active_generations(user: UserResponse = Depends(current_user)) -> list[ActiveGeneration]:
    rows = [
        *(
            {
                "kind": "image",
                "prompt_id": generation["prompt_id"],
                "client_id": generation["client_id"],
                "generation_id": str(generation["id"]),
                "status": generation["status"],
                "created_at": generation["created_at"],
            }
            for generation in list_active_image_generations(user.id)
        ),
        *(
            {
                "kind": "video",
                "prompt_id": generation["prompt_id"],
                "client_id": generation["client_id"],
                "generation_id": str(generation["id"]),
                "mode": generation["mode"],
                "status": generation["status"],
                "created_at": generation["created_at"],
            }
            for generation in list_active_video_generations(user.id)
        ),
    ]
    return [ActiveGeneration.model_validate(row) for row in sorted(rows, key=lambda row: row["created_at"])]
