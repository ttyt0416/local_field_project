from __future__ import annotations

import json
from time import monotonic
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from .configs.constants import settings

_STORAGE_TIMEOUT_SECONDS = 30
_READ_URL_CACHE_MARGIN_SECONDS = 30
_READ_URL_CACHE_MAX_ENTRIES = 512
_read_url_cache: dict[tuple[str, str, int], tuple[float, str]] = {}


class StorageError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def enabled() -> bool:
    return bool(settings.storage_url and settings.storage_api_token)


def upload_file(*, content: bytes, media_type: str, owner_id: str) -> str:
    if not enabled():
        raise StorageError("스토리지 설정이 없습니다.")
    response = _request_json(
        "POST",
        "/files",
        data=content,
        headers={
            "Authorization": f"Bearer {settings.storage_api_token}",
            "Content-Type": media_type or "application/octet-stream",
            "X-Owner-ID": owner_id,
        },
    )
    file_id = response.get("id")
    if not isinstance(file_id, str) or not file_id:
        raise StorageError("스토리지가 파일 ID를 반환하지 않았습니다.")
    return file_id


def read_url(*, file_id: str, owner_id: str, expires_in: int = 900) -> str:
    if not enabled():
        raise StorageError("스토리지 설정이 없습니다.")
    cache_key = (file_id, owner_id, expires_in)
    now = monotonic()
    cached = _read_url_cache.get(cache_key)
    if cached is not None:
        cached_until, cached_url = cached
        if cached_until > now:
            return cached_url
        _read_url_cache.pop(cache_key, None)
    path = f"/files/{quote(file_id, safe='')}/url?{urlencode({'expires_in': expires_in})}"
    response = _request_json(
        "POST",
        path,
        headers={
            "Authorization": f"Bearer {settings.storage_api_token}",
            "X-Owner-ID": owner_id,
        },
    )
    url = response.get("url")
    if not isinstance(url, str) or not url:
        raise StorageError("스토리지가 파일 읽기 URL을 반환하지 않았습니다.")
    if len(_read_url_cache) >= _READ_URL_CACHE_MAX_ENTRIES:
        _read_url_cache.pop(next(iter(_read_url_cache)))
    _read_url_cache[cache_key] = (now + max(expires_in - _READ_URL_CACHE_MARGIN_SECONDS, 1), url)
    return url


def download_file(*, file_id: str, owner_id: str) -> tuple[bytes, str]:
    public_url = read_url(file_id=file_id, owner_id=owner_id, expires_in=300)
    signed = urlsplit(public_url)
    internal = urlsplit(settings.storage_url)
    url = urlunsplit((internal.scheme, internal.netloc, signed.path, signed.query, ""))
    try:
        with urlopen(UrlRequest(url), timeout=_STORAGE_TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get_content_type()
    except UrlHTTPError as exc:
        raise StorageError(f"스토리지 파일 읽기가 실패했습니다. (HTTP {exc.code})", status_code=exc.code) from exc
    except (URLError, TimeoutError) as exc:
        raise StorageError("스토리지 파일을 읽을 수 없습니다.") from exc



def _invalidate_read_url_cache(file_id: str, owner_id: str) -> None:
    for cache_key in tuple(_read_url_cache):
        if cache_key[:2] == (file_id, owner_id):
            _read_url_cache.pop(cache_key, None)


def delete_file(*, file_id: str, owner_id: str) -> None:
    if not enabled():
        raise StorageError("스토리지 설정이 없습니다.")
    try:
        _request_json(
            "DELETE",
            f"/files/{quote(file_id, safe='')}",
            headers={
                "Authorization": f"Bearer {settings.storage_api_token}",
                "X-Owner-ID": owner_id,
            },
            allow_empty=True,
        )
    except StorageError as exc:
        if exc.status_code == 404:
            _invalidate_read_url_cache(file_id, owner_id)
            return
        raise
    _invalidate_read_url_cache(file_id, owner_id)


def _request_json(
    method: str,
    path: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str],
    allow_empty: bool = False,
) -> dict:
    request = UrlRequest(
        f"{settings.storage_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=_STORAGE_TIMEOUT_SECONDS) as response:
            body = response.read()
            if not body and allow_empty:
                return {}
            decoded = json.loads(body)
    except UrlHTTPError as exc:
        raise StorageError(f"스토리지 요청이 실패했습니다. (HTTP {exc.code})", status_code=exc.code) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise StorageError("스토리지에 연결할 수 없습니다.") from exc
    if not isinstance(decoded, dict):
        raise StorageError("스토리지 응답 형식이 올바르지 않습니다.")
    return decoded
