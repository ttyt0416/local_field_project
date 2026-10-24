from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import UserResponse, current_user
from .danbooru import DanbooruTagPage, DanbooruTagResponse, _like_escape
from .database import get_connection


router = APIRouter(prefix="/tags/gelbooru", tags=["Gelbooru local tags"])


def list_tags(search: str, category: int | None, sort: str, page: int) -> tuple[list[dict], int]:
    term = re.sub(r"\s+", "_", search.strip().casefold())
    parameters = []
    clauses = []
    if term:
        clauses.append("normalized_tag LIKE %s ESCAPE '\\'")
        parameters.append(f"%{_like_escape(term)}%")
    if category is not None:
        clauses.append("category = %s")
        parameters.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "post_count DESC, tag ASC"
    ordering = []
    if term and sort == "match":
        order = "CASE WHEN normalized_tag = %s THEN 0 WHEN normalized_tag LIKE %s ESCAPE '\\' THEN 1 ELSE 2 END, " + order
        ordering = [term, f"{_like_escape(term)}%"]
    with get_connection() as connection:
        state = connection.execute("SELECT imported_at FROM tag_catalogue_imports WHERE source = 'gelbooru'").fetchone()
        if state is None or state[0] is None:
            raise HTTPException(status_code=503, detail="Gelbooru 로컬 태그 데이터가 아직 준비되지 않았습니다.")
        count = connection.execute(f"SELECT COUNT(*) FROM gelbooru_tags {where}", parameters).fetchone()[0]
        rows = connection.execute(f"SELECT tag, category, post_count FROM gelbooru_tags {where} ORDER BY {order} LIMIT 50 OFFSET %s", [*parameters, *ordering, (page - 1) * 50]).fetchall()
    return [{"tag": row[0], "category": row[1], "post_count": row[2], "aliases": []} for row in rows], count


@router.get("", response_model=DanbooruTagPage)
def browse_tags(search: str = Query(default="", max_length=120), category: int | None = Query(default=None, ge=0, le=6), sort: Literal["match", "usage"] = "match", page: int = Query(default=1, ge=1), _: UserResponse = Depends(current_user)) -> DanbooruTagPage:
    items, count = list_tags(search, category, sort, page)
    return DanbooruTagPage(items=[DanbooruTagResponse(**item) for item in items], page=page, page_size=50, total_count=count, total_pages=(count + 49) // 50)


def import_tags(path: Path) -> int:
    with get_connection() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('local-field-gelbooru-import'))")
        connection.execute("CREATE TEMP TABLE gelbooru_import (tag TEXT, normalized_tag TEXT, category SMALLINT, post_count INTEGER) ON COMMIT DROP")
        with path.open(encoding="utf-8-sig") as source, connection.cursor() as cursor, cursor.copy("COPY gelbooru_import (tag, normalized_tag, category, post_count) FROM STDIN") as copy:
            for line in source:
                row = json.loads(line)
                tag = row.get("tag_name")
                category = row.get("category_id")
                count = row.get("post_count")
                if not isinstance(tag, str) or not tag or len(tag) > 512 or "\x00" in tag:
                    continue
                if isinstance(category, bool) or not isinstance(category, int) or category not in range(7) or isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 2147483647:
                    raise ValueError("Gelbooru 태그 행의 분류 또는 사용 수가 올바르지 않습니다.")
                copy.write_row((tag, tag.casefold(), category, count))
        count = connection.execute("SELECT COUNT(*) FROM gelbooru_import").fetchone()[0]
        if not count:
            raise ValueError("가져올 Gelbooru 태그가 없습니다.")
        connection.execute("DELETE FROM gelbooru_tags")
        connection.execute("INSERT INTO gelbooru_tags SELECT DISTINCT ON (tag) tag, normalized_tag, category, post_count FROM gelbooru_import ORDER BY tag, post_count DESC")
        connection.execute("""INSERT INTO tag_catalogue_imports (source, version, imported_at) VALUES ('gelbooru', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (source) DO UPDATE SET version = EXCLUDED.version, imported_at = EXCLUDED.imported_at, last_attempt_at = CURRENT_TIMESTAMP, error_message = NULL""", (path.name,))
        total = connection.execute("SELECT COUNT(*) FROM gelbooru_tags").fetchone()[0]
        connection.execute("DROP TABLE pg_temp.gelbooru_import")
        return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import a local Gelbooru tag JSONL snapshot.")
    parser.add_argument("path", type=Path)
    print(f"imported_tags={import_tags(parser.parse_args().path)}")
