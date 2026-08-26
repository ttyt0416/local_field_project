from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from .configs.constants import settings
from .database import get_connection


def search_danbooru_tags(text: str, limit: int = 48) -> list[str]:
    embedding = _request_embeddings([text])[0]
    vector = _vector_literal(embedding)
    vector_limit = max(1, limit - 32)
    tokens = _search_tokens(text)
    with get_connection() as connection:
        vector_rows = connection.execute(
            """
            SELECT tag
            FROM danbooru_tags
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, vector_limit),
        ).fetchall()
        exact_rows = connection.execute(
            """
            SELECT tag
            FROM danbooru_tags
            WHERE normalized_tag = ANY(%s)
               OR EXISTS (
                    SELECT 1
                    FROM unnest(aliases) AS alias
                    WHERE lower(alias) = ANY(%s)
               )
            ORDER BY post_count DESC
            LIMIT %s
            """,
            (tokens, tokens, 32),
        ).fetchall()
        popular_rows = connection.execute(
            "SELECT tag FROM danbooru_tags ORDER BY post_count DESC LIMIT %s",
            (32,),
        ).fetchall()
    tags = _unique_tags(
        [row[0] for row in exact_rows]
        + [row[0] for row in vector_rows]
        + [row[0] for row in popular_rows]
    )[:limit]
    if not tags:
        raise DanbooruError("Danbooru 태그 벡터가 아직 준비되지 않았습니다.")
    return tags


def _search_tokens(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[a-z0-9_]+|[가-힣]{2,}", text.lower())))


def _unique_tags(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return result


def validate_danbooru_tags(contents: str) -> list[str]:
    candidates = _tag_candidates(contents)
    if not candidates:
        return []
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT tag FROM danbooru_tags WHERE tag = ANY(%s)",
            (candidates,),
        ).fetchall()
    valid = {row[0] for row in rows if isinstance(row[0], str)}
    return [tag for tag in candidates if tag in valid]


def import_danbooru_tags(csv_path: str | Path, batch_size: int = 64) -> int:
    path = Path(csv_path)
    if not path.is_file():
        raise DanbooruError(f"Danbooru CSV를 찾을 수 없습니다: {path}")

    imported = 0
    with get_connection() as connection, path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for rows in _batches(_csv_rows(reader), batch_size):
            embeddings = _request_embeddings([_embedding_text(row) for row in rows])
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO danbooru_tags
                        (tag, normalized_tag, category, post_count, aliases, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (tag) DO UPDATE SET
                        normalized_tag = EXCLUDED.normalized_tag,
                        category = EXCLUDED.category,
                        post_count = EXCLUDED.post_count,
                        aliases = EXCLUDED.aliases,
                        embedding = EXCLUDED.embedding,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    [
                        (
                            row["tag"],
                            row["tag"].lower(),
                            row["category"],
                            row["post_count"],
                            row["aliases"],
                            _vector_literal(embedding),
                        )
                        for row, embedding in zip(rows, embeddings, strict=True)
                    ],
                )
            imported += len(rows)
            print(f"imported={imported}", flush=True)
    return imported


def _csv_rows(reader: csv.DictReader[str]) -> Iterator[dict[str, Any]]:
    for raw in reader:
        tag = (raw.get("tag") or "").strip().lower()
        if not tag:
            continue
        try:
            category = int(raw.get("category") or 0)
            post_count = int(raw.get("count") or 0)
        except ValueError:
            continue
        aliases = [alias.strip() for alias in (raw.get("alias") or "").split(",") if alias.strip()]
        yield {
            "tag": tag,
            "category": category,
            "post_count": post_count,
            "aliases": aliases,
        }


def _batches(items: Iterator[dict[str, Any]], batch_size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _embedding_text(row: dict[str, Any]) -> str:
    aliases = ", ".join(row["aliases"][:24])
    return f"Danbooru tag: {row['tag']}. Aliases: {aliases}. Category: {row['category']}."


def _request_embeddings(texts: Sequence[str]) -> list[list[float]]:
    payload = {
        "model": settings.embedding_model,
        "input": list(texts),
        "encoding_format": "float",
    }
    request = UrlRequest(
        f"{settings.embedding_url.rstrip('/')}/v1/embeddings",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            decoded = json.loads(response.read())
    except UrlHTTPError as exc:
        raise DanbooruError(f"임베딩 모델 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DanbooruError("임베딩 모델에 연결할 수 없습니다.") from exc
    data = decoded.get("data") if isinstance(decoded, dict) else None
    if not isinstance(data, list) or len(data) != len(texts):
        raise DanbooruError("임베딩 모델 응답 형식이 올바르지 않습니다.")
    ordered = sorted(data, key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0)
    vectors = [item.get("embedding") for item in ordered if isinstance(item, dict)]
    if len(vectors) != len(texts) or any(not _valid_embedding(vector) for vector in vectors):
        raise DanbooruError("임베딩 벡터 형식이 올바르지 않습니다.")
    return vectors


def _valid_embedding(value: Any) -> bool:
    return isinstance(value, list) and len(value) == settings.embedding_dimensions and all(
        isinstance(number, (int, float)) for number in value
    )


def _vector_literal(values: Sequence[float]) -> str:
    if len(values) != settings.embedding_dimensions:
        raise DanbooruError("임베딩 차원이 설정과 다릅니다.")
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


def _tag_candidates(contents: str) -> list[str]:
    result: list[str] = []
    for raw in re.split(r"[,\n]+", contents):
        tag = raw.strip().strip("`'\"-* ").lower().replace(" ", "_")
        if tag and tag not in result:
            result.append(tag)
    return result


class DanbooruError(RuntimeError):
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Danbooru tags and embeddings into PostgreSQL.")
    parser.add_argument("--csv", default=settings.danbooru_tags_path)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    print(f"imported_total={import_danbooru_tags(args.csv, max(1, args.batch_size))}")


if __name__ == "__main__":
    main()
