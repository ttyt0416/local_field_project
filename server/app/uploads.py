from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .database import delete_media_asset, get_media_asset, list_reusable_media
from .storage import (
    StorageError,
    delete_file as storage_delete_file,
    enabled as storage_enabled,
    read_url as storage_read_url,
)


router = APIRouter(prefix="/uploads", tags=["media library"])
UPLOADS_PAGE_SIZE = 10


class MediaAssetResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    media_kind: Literal["image", "audio", "video"]
    source_type: str
    url: str | None
    created_at: datetime


class MediaAssetPage(BaseModel):
    items: list[MediaAssetResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    file_id: str,
    user: UserResponse = Depends(current_user),
) -> Response:
    asset = get_media_asset(file_id, user.id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업로드 콘텐츠를 찾을 수 없습니다.")
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
) -> MediaAssetPage:
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
