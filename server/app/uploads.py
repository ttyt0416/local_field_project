from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .database import list_reusable_media
from .storage import StorageError, enabled as storage_enabled, read_url as storage_read_url


router = APIRouter(prefix="/uploads", tags=["media library"])


class MediaAssetResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    media_kind: Literal["image", "audio", "video"]
    source_type: str
    url: str | None
    created_at: datetime


@router.get("", response_model=list[MediaAssetResponse])
def reusable_media(
    search: str = Query(default="", max_length=200),
    sort: Literal["latest", "oldest", "name"] = "latest",
    include_generated: bool = False,
    media_kind: Literal["image", "audio", "video"] | None = None,
    user: UserResponse = Depends(current_user),
) -> list[MediaAssetResponse]:
    if not storage_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="스토리지 설정이 없습니다.")
    result: list[MediaAssetResponse] = []
    for asset in list_reusable_media(
        user.id,
        search=search,
        sort=sort,
        include_generated=include_generated,
        media_kind=media_kind,
    ):
        url = None
        try:
            url = storage_read_url(file_id=asset["file_id"], owner_id=str(user.id))
        except StorageError:
            # A stale object remains visible without a preview until it is repaired or removed.
            pass
        result.append(MediaAssetResponse(**asset, url=url))
    return result
