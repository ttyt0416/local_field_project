from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .comfyui import generation_progress
from .database import generation_elapsed_seconds, list_active_image_generations, list_active_video_generations


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
    progress: float = 0
    queue_position: int | None = None
    created_at: datetime
    elapsed_seconds: float = 0


@router.get("/active", response_model=list[ActiveGeneration])
def active_generations(user: UserResponse = Depends(current_user)) -> list[ActiveGeneration]:
    def active_fields(generation: dict[str, Any]) -> dict[str, Any]:
        progress = generation_progress(generation["prompt_id"], user.id)
        return {
            "progress": progress["progress"],
            "queue_position": progress["queue_position"],
            "elapsed_seconds": generation_elapsed_seconds(generation),
        }

    rows = [
        *(
            {
                "kind": "image",
                "prompt_id": generation["prompt_id"],
                "client_id": generation["client_id"],
                "generation_id": str(generation["id"]),
                "status": generation["status"],
                **active_fields(generation),
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
                **active_fields(generation),
                "created_at": generation["created_at"],
            }
            for generation in list_active_video_generations(user.id)
        ),
    ]
    return [ActiveGeneration.model_validate(row) for row in sorted(rows, key=lambda row: row["created_at"])]
