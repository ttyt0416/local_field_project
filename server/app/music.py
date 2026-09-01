from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import UserResponse, current_user


router = APIRouter(prefix="/generation/music", tags=["music generation"])


class MusicGenerationOptions(BaseModel):
    model: Literal["MiniMax-Music3"]
    service_available: bool
    detail: str


@router.get("/options", response_model=MusicGenerationOptions)
def music_options(_: UserResponse = Depends(current_user)) -> MusicGenerationOptions:
    return MusicGenerationOptions(
        model="MiniMax-Music3",
        service_available=False,
        detail="MiniMax Music 3 local service 연결 전입니다.",
    )
