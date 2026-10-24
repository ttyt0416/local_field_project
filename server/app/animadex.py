from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .danbooru import _like_escape
from .database import get_connection, record_api_call, record_api_error


router = APIRouter(prefix="/tags/catalogue", tags=["AnimaDex local catalogue"])
CatalogueKind = Literal["characters", "artists", "series"]
CatalogueSort = Literal["count", "name"]
_SITE = "https://animadex.net"


class CatalogueImportError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


_OPENER = build_opener(_NoRedirect)


class CatalogueEntry(BaseModel):
    slug: str
    name: str
    trigger: str
    tags: list[str]
    copyright: str | None
    copyright_name: str | None
    count: int
    thumb_url: str | None = None
    source_url: str


class CataloguePage(BaseModel):
    items: list[CatalogueEntry]
    page: int
    page_size: int = 48
    total_count: int
    total_pages: int
    source: Literal["local"] = "local"
    catalogue_version: str
    imported_at: datetime
    warning: str | None = None


def _read_url(url: str, *, token: str = "", manifest: bool = False) -> bytes:
    parsed = urlparse(url)
    expected = "animadex.net" if manifest else "blobs.animadex.net"
    if parsed.scheme != "https" or parsed.netloc != expected or (manifest and parsed.path != "/api/export/manifest"):
        raise CatalogueImportError("AnimaDex 내보내기 주소가 올바르지 않습니다.")
    headers = {"User-Agent": "LocalField/0.1"}
    if token:
        if not manifest or len(token) > 4096 or any(not 33 <= ord(char) <= 126 for char in token):
            raise CatalogueImportError("AnimaDex 토큰 설정이 올바르지 않습니다.")
        headers["X-Export-Token"] = token
    limit = 1024 * 1024 if manifest else 64 * 1024 * 1024
    code = 502
    try:
        with _OPENER.open(Request(url, headers=headers), timeout=45) as response:
            code = response.status
            raw = response.read(limit + 1)
        if len(raw) > limit:
            raise CatalogueImportError("AnimaDex 내보내기 파일이 허용 크기를 초과했습니다.")
        return raw
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise CatalogueImportError(f"AnimaDex 내보내기 요청이 실패했습니다. (HTTP {code})") from None
    except (URLError, OSError, TimeoutError):
        raise CatalogueImportError("AnimaDex CSV 서버의 TLS 또는 네트워크 연결 오류로 로컬 카탈로그를 가져오지 못했습니다.") from None
    finally:
        path = "/upstream/animadex/export/manifest" if manifest else "/upstream/animadex/export/csv"
        record_api_call(method="GET", path=path, status_code=code, client_ip=None, user_agent="LocalField/0.1", user_id=None)
        if code >= 400:
            record_api_error(method="GET", path=path, status_code=code, error_type="CatalogueImportError", error_message="AnimaDex export request failed", client_ip=None, user_agent="LocalField/0.1", user_id=None)


def _csv(raw: bytes, required: set[str]) -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not required.issubset(reader.fieldnames or []):
            raise CatalogueImportError("AnimaDex CSV의 필수 필드가 없습니다.")
        return list(reader)
    except (UnicodeError, csv.Error):
        raise CatalogueImportError("AnimaDex CSV 파일을 읽지 못했습니다.") from None


def _number(value: str | None) -> int:
    try:
        number = int(value or 0)
    except (ValueError, TypeError):
        raise CatalogueImportError("AnimaDex CSV의 사용 수가 올바르지 않습니다.") from None
    if not 0 <= number <= 2147483647:
        raise CatalogueImportError("AnimaDex CSV의 사용 수가 범위를 초과했습니다.")
    return number


def _build_entries(characters: list[dict], artists: list[dict]) -> list[tuple]:
    entries = {}
    series = {}
    for kind, rows, key in (("characters", characters, "character"), ("artists", artists, "artist")):
        if not rows:
            raise CatalogueImportError("빈 AnimaDex CSV로 기존 카탈로그를 교체할 수 없습니다.")
        for row in rows:
            slug = (row.get(key) or "").strip()
            trigger = (row.get("trigger") or slug.replace("_", " ")).strip()
            if not slug or len(slug) > 512 or not trigger or len(trigger) > 5000 or any("\x00" in str(value) for value in row.values()):
                raise CatalogueImportError("AnimaDex CSV에 올바르지 않은 항목이 있습니다.")
            copyright = (row.get("copyright") or "").strip() or None
            copyright_name = (row.get("copyright_name") or (copyright or "").replace("_", " ")).strip() or None
            name = (row.get("name") or trigger.split(",", 1)[0]).strip()
            tags = [tag.strip() for tag in (row.get("core_tags") or "").split(",") if tag.strip()]
            search = " ".join([slug, name, trigger, copyright or "", copyright_name or "", *tags]).replace("_", " ").casefold()
            entries[(kind, slug)] = (kind, slug, name, trigger, tags, copyright, copyright_name, _number(row.get("count")), search)
    for entry in entries.values():
        if entry[0] == "characters" and entry[5]:
            group = series.setdefault(entry[5], {"name": entry[6], "count": 0})
            group["count"] += 1
    for slug, group in series.items():
        name = group["name"] or slug.replace("_", " ")
        entries[("series", slug)] = ("series", slug, name, slug.replace("_", " "), [], None, None, group["count"], f"{slug} {name}".replace("_", " ").casefold())
    return list(entries.values())


def import_catalogue(characters_raw: bytes, artists_raw: bytes, version: str) -> dict[str, int]:
    entries = _build_entries(_csv(characters_raw, {"character", "copyright", "trigger", "core_tags"}), _csv(artists_raw, {"artist"}))
    with get_connection() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('local-field-animadex-import'))")
        connection.execute("CREATE TEMP TABLE animadex_import (LIKE animadex_entries) ON COMMIT DROP")
        with connection.cursor() as cursor, cursor.copy("COPY animadex_import (kind, slug, name, trigger, tags, copyright, copyright_name, post_count, search_text) FROM STDIN") as copy:
            for entry in entries:
                copy.write_row(entry)
        connection.execute("DELETE FROM animadex_entries")
        connection.execute("INSERT INTO animadex_entries SELECT * FROM animadex_import")
        connection.execute("DROP TABLE pg_temp.animadex_import")
        connection.execute("""INSERT INTO tag_catalogue_imports (source, version, imported_at) VALUES ('animadex', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (source) DO UPDATE SET version = EXCLUDED.version, imported_at = EXCLUDED.imported_at, last_attempt_at = CURRENT_TIMESTAMP, error_message = NULL""", (version,))
    return {kind: sum(entry[0] == kind for entry in entries) for kind in ("characters", "artists", "series")}


def sync_catalogue() -> dict[str, int]:
    try:
        token = os.environ.get("ANIMADEX_EXPORT_TOKEN", "").strip()
        if not token:
            raise CatalogueImportError("서버에 AnimaDex export 토큰을 설정해 주세요.")
        manifest = json.loads(_read_url(f"{_SITE}/api/export/manifest", token=token, manifest=True))
        if not isinstance(manifest, dict) or not manifest.get("ok") or not isinstance(manifest.get("csv"), dict) or not isinstance(manifest.get("version"), (str, int)):
            raise CatalogueImportError("AnimaDex 카탈로그 manifest 형식이 올바르지 않습니다.")
        files = manifest["csv"]
        if not all(isinstance(files.get(key), str) for key in ("characters", "artists")):
            raise CatalogueImportError("AnimaDex 카탈로그 CSV 주소가 없습니다.")
        return import_catalogue(_read_url(files["characters"]), _read_url(files["artists"]), str(manifest["version"]))
    except (CatalogueImportError, ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, CatalogueImportError) else "AnimaDex 내보내기 파일 형식이 올바르지 않습니다."
        with get_connection() as connection:
            connection.execute("""INSERT INTO tag_catalogue_imports (source, error_message) VALUES ('animadex', %s)
                ON CONFLICT (source) DO UPDATE SET last_attempt_at = CURRENT_TIMESTAMP, error_message = EXCLUDED.error_message""", (message,))
        raise CatalogueImportError(message) from None


def search_catalogue(kind: CatalogueKind, search: str, sort: CatalogueSort, page: int, series: str) -> CataloguePage:
    term = re.sub(r"\s+", " ", search.strip().replace("_", " ").casefold())
    clauses = ["kind = %s"]
    parameters = [kind]
    if term:
        clauses.append("search_text LIKE %s ESCAPE '\\'")
        parameters.append(f"%{_like_escape(term)}%")
    if series and kind == "characters":
        clauses.append("copyright = %s")
        parameters.append(series)
    where = " AND ".join(clauses)
    ordering = "name ASC, slug ASC" if sort == "name" else "post_count DESC, name ASC, slug ASC"
    with get_connection() as connection:
        state = connection.execute("SELECT version, imported_at, error_message FROM tag_catalogue_imports WHERE source = 'animadex'").fetchone()
        if state is None or state[1] is None:
            message = state[2] if state and state[2] else "AnimaDex 로컬 카탈로그가 아직 준비되지 않았습니다."
            raise HTTPException(status_code=503, detail=message)
        count = connection.execute(f"SELECT COUNT(*) FROM animadex_entries WHERE {where}", parameters).fetchone()[0]
        rows = connection.execute(f"SELECT slug, name, trigger, tags, copyright, copyright_name, post_count FROM animadex_entries WHERE {where} ORDER BY {ordering} LIMIT 48 OFFSET %s", [*parameters, (page - 1) * 48]).fetchall()
    items = [CatalogueEntry(slug=row[0], name=row[1], trigger=row[2], tags=list(row[3]), copyright=row[4], copyright_name=row[5], count=row[6], source_url=f"{_SITE}/?{urlencode({'mode': 'copyrights' if kind == 'series' else kind, 'q': row[0]})}") for row in rows]
    return CataloguePage(items=items, page=page, total_count=count, total_pages=(count + 47) // 48, catalogue_version=state[0], imported_at=state[1], warning=state[2])


@router.get("/{kind}", response_model=CataloguePage)
def browse_catalogue(kind: CatalogueKind, search: str = Query(default="", max_length=120), sort: CatalogueSort = "count", page: int = Query(default=1, ge=1, le=10000), series: str = Query(default="", max_length=512), _: UserResponse = Depends(current_user)) -> CataloguePage:
    return search_catalogue(kind, search, sort, page, series)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import AnimaDex metadata for local-only catalogue search.")
    parser.add_argument("--csv-dir", type=Path)
    parser.add_argument("--version", default="manual")
    args = parser.parse_args()
    try:
        result = import_catalogue((args.csv_dir / 'characters.csv').read_bytes(), (args.csv_dir / 'artists.csv').read_bytes(), args.version) if args.csv_dir else sync_catalogue()
        print(json.dumps(result))
    except CatalogueImportError as exc:
        print(str(exc))
        raise SystemExit(1)
