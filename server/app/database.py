from collections.abc import Iterable
from datetime import datetime, timezone
import json
from typing import Any
import uuid

import psycopg

from .configs.constants import DEFAULT_EMBEDDING_DIMENSIONS, settings


_MIGRATION_STATEMENTS: tuple[str, ...] = (
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'email'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'username'
        ) THEN
            ALTER TABLE users RENAME COLUMN email TO username;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'auth_history' AND column_name = 'email'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'auth_history' AND column_name = 'username'
        ) THEN
            ALTER TABLE auth_history RENAME COLUMN email TO username;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'image_generations'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'loras'
            ) THEN
                ALTER TABLE image_generations ADD COLUMN loras JSONB NOT NULL DEFAULT '[]'::jsonb;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'lora'
            ) THEN
                ALTER TABLE image_generations DROP COLUMN lora;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'lora_strength'
            ) THEN
                ALTER TABLE image_generations DROP COLUMN lora_strength;
            END IF;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'image_generations'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'storage_file_id'
        ) THEN
            ALTER TABLE image_generations ADD COLUMN storage_file_id TEXT;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'presets'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'presets' AND column_name = 'is_default'
        ) THEN
            ALTER TABLE presets ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'presets'
        ) THEN
            ALTER TABLE presets DROP CONSTRAINT IF EXISTS presets_user_id_type_name_key;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'image_generations'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'view_count'
            ) THEN
                ALTER TABLE image_generations ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'is_favorite'
            ) THEN
                ALTER TABLE image_generations ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'video_generations'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'video_generations' AND column_name = 'view_count'
            ) THEN
                ALTER TABLE video_generations ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'video_generations' AND column_name = 'is_favorite'
            ) THEN
                ALTER TABLE video_generations ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'image_generations'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'elapsed_seconds'
            ) THEN
                ALTER TABLE image_generations ADD COLUMN elapsed_seconds DOUBLE PRECISION NOT NULL DEFAULT 0;
            END IF;
            UPDATE image_generations
            SET elapsed_seconds = GREATEST(0, EXTRACT(EPOCH FROM (COALESCE(completed_at, CURRENT_TIMESTAMP) - created_at)))
            WHERE elapsed_seconds = 0;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'video_generations'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'video_generations' AND column_name = 'elapsed_seconds'
            ) THEN
                ALTER TABLE video_generations ADD COLUMN elapsed_seconds DOUBLE PRECISION NOT NULL DEFAULT 0;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'video_generations' AND column_name = 'fps'
            ) THEN
                ALTER TABLE video_generations ADD COLUMN fps DOUBLE PRECISION NOT NULL DEFAULT 24;
            END IF;
            UPDATE video_generations
            SET elapsed_seconds = GREATEST(0, EXTRACT(EPOCH FROM (COALESCE(completed_at, CURRENT_TIMESTAMP) - created_at)))
            WHERE elapsed_seconds = 0;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'image_generations'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'source_generation_id'
            ) THEN
                ALTER TABLE image_generations ADD COLUMN source_generation_id UUID;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'is_edited'
            ) THEN
                ALTER TABLE image_generations ADD COLUMN is_edited BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'image_generations' AND column_name = 'size_bytes'
            ) THEN
                ALTER TABLE image_generations ADD COLUMN size_bytes BIGINT NOT NULL DEFAULT 0;
            END IF;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'video_generations'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'video_generations' AND column_name = 'source_generation_id'
            ) THEN
                ALTER TABLE video_generations ADD COLUMN source_generation_id UUID;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'video_generations' AND column_name = 'is_edited'
            ) THEN
                ALTER TABLE video_generations ADD COLUMN is_edited BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'video_generations' AND column_name = 'size_bytes'
            ) THEN
                ALTER TABLE video_generations ADD COLUMN size_bytes BIGINT NOT NULL DEFAULT 0;
            END IF;
        END IF;
    END
    $$
    """,
)


_SCHEMA_STATEMENTS: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    f"""
    CREATE TABLE IF NOT EXISTS danbooru_tags (
        id BIGSERIAL PRIMARY KEY,
        tag TEXT UNIQUE NOT NULL,
        normalized_tag TEXT NOT NULL,
        category SMALLINT NOT NULL,
        post_count INTEGER NOT NULL DEFAULT 0,
        aliases TEXT[] NOT NULL DEFAULT '{{}}',
        embedding vector({DEFAULT_EMBEDDING_DIMENSIONS}),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS danbooru_tags_normalized_idx ON danbooru_tags(normalized_tag)",
    "CREATE INDEX IF NOT EXISTS danbooru_tags_aliases_gin_idx ON danbooru_tags USING gin (aliases)",
    """
    CREATE INDEX IF NOT EXISTS danbooru_tags_embedding_hnsw_idx
    ON danbooru_tags USING hnsw (embedding vector_cosine_ops)
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY,
        username VARCHAR(32) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_history (
        id BIGSERIAL PRIMARY KEY,
        event_type VARCHAR(32) NOT NULL,
        username VARCHAR(32),
        success BOOLEAN NOT NULL,
        failure_reason VARCHAR(128),
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        client_ip TEXT,
        user_agent TEXT,
        user_id UUID REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS auth_history_user_id_idx ON auth_history(user_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS presets (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        type VARCHAR(16) NOT NULL,
        name VARCHAR(100) NOT NULL,
        values JSONB NOT NULL DEFAULT '{}'::jsonb,
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS presets_user_type_idx ON presets(user_id, type, updated_at DESC)",
    "CREATE UNIQUE INDEX IF NOT EXISTS presets_one_default_per_user_type_idx ON presets(user_id, type) WHERE is_default",
    """
    CREATE TABLE IF NOT EXISTS image_generations (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        prompt_id VARCHAR(128) UNIQUE NOT NULL,
        client_id VARCHAR(128) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'queued',
        prompt TEXT NOT NULL,
        negative_prompt TEXT NOT NULL,
        checkpoint VARCHAR(255) NOT NULL,
        loras JSONB NOT NULL DEFAULT '[]'::jsonb,
        cfg DOUBLE PRECISION NOT NULL,
        steps INTEGER NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        seed BIGINT NOT NULL,
        file_path TEXT,
        storage_file_id TEXT,
        filename VARCHAR(255),
        subfolder VARCHAR(255) NOT NULL DEFAULT '',
        image_type VARCHAR(32) NOT NULL DEFAULT 'output',
        view_count INTEGER NOT NULL DEFAULT 0,
        is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMPTZ,
        elapsed_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
        source_generation_id UUID,
        is_edited BOOLEAN NOT NULL DEFAULT FALSE,
        size_bytes BIGINT NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS image_generations_user_id_idx ON image_generations(user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS image_generations_prompt_trgm_idx
    ON image_generations USING gin (prompt gin_trgm_ops)
    """,
    """
    CREATE TABLE IF NOT EXISTS media_assets (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        storage_file_id TEXT UNIQUE NOT NULL,
        filename VARCHAR(255) NOT NULL,
        content_type VARCHAR(128) NOT NULL,
        media_kind VARCHAR(16) NOT NULL,
        size BIGINT NOT NULL,
        source_type VARCHAR(32) NOT NULL DEFAULT 'generation_input',
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS media_assets_user_created_idx ON media_assets(user_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS video_generations (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        prompt_id VARCHAR(128) UNIQUE NOT NULL,
        client_id VARCHAR(128) NOT NULL,
        mode VARCHAR(8) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'queued',
        prompt TEXT NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        length INTEGER NOT NULL,
        fps DOUBLE PRECISION NOT NULL DEFAULT 24,
        seed BIGINT NOT NULL,
        input_file_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        storage_file_id TEXT,
        filename VARCHAR(255),
        subfolder VARCHAR(255) NOT NULL DEFAULT '',
        video_type VARCHAR(32) NOT NULL DEFAULT 'output',
        view_count INTEGER NOT NULL DEFAULT 0,
        is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMPTZ,
        elapsed_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
        source_generation_id UUID,
        is_edited BOOLEAN NOT NULL DEFAULT FALSE,
        size_bytes BIGINT NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS video_generations_user_created_idx ON video_generations(user_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS model_downloads (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        version_id BIGINT NOT NULL,
        model_type VARCHAR(32) NOT NULL,
        file_index INTEGER NOT NULL DEFAULT 0,
        filename VARCHAR(255) NOT NULL,
        target_path TEXT NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'queued',
        downloaded_bytes BIGINT NOT NULL DEFAULT 0,
        total_bytes BIGINT,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS model_downloads_status_created_idx ON model_downloads(status, created_at)",
    "CREATE INDEX IF NOT EXISTS model_downloads_user_created_idx ON model_downloads(user_id, created_at DESC)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS model_downloads_active_unique_idx
    ON model_downloads(user_id, version_id, model_type, file_index)
    WHERE status IN ('queued', 'downloading')
    """,
    """
    CREATE TABLE IF NOT EXISTS api_audit_logs (
        id BIGSERIAL PRIMARY KEY,
        method VARCHAR(16) NOT NULL,
        path TEXT NOT NULL,
        status_code SMALLINT NOT NULL,
        requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        client_ip TEXT,
        user_agent TEXT,
        user_id UUID REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS api_error_logs (
        id BIGSERIAL PRIMARY KEY,
        method VARCHAR(16) NOT NULL,
        path TEXT NOT NULL,
        status_code SMALLINT NOT NULL,
        error_type VARCHAR(128) NOT NULL,
        error_message TEXT NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        client_ip TEXT,
        user_agent TEXT,
        user_id UUID REFERENCES users(id) ON DELETE SET NULL
    )
    """,
)


_WEB_LOG_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS web_event_logs (
        id BIGSERIAL PRIMARY KEY,
        event_type VARCHAR(32) NOT NULL,
        page_path TEXT NOT NULL,
        from_path TEXT,
        target_type VARCHAR(32) NOT NULL,
        target_id TEXT,
        target_label TEXT,
        target_href TEXT,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        client_ip TEXT,
        user_agent TEXT,
        user_id UUID
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS web_event_logs_page_path_idx ON web_event_logs(page_path)
    """,
    """
    CREATE INDEX IF NOT EXISTS web_event_logs_user_id_idx ON web_event_logs(user_id)
    """,
)


def get_connection() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


def get_web_log_connection() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=settings.web_log_db_host,
        port=settings.web_log_db_port,
        dbname=settings.web_log_postgres_db,
        user=settings.web_log_postgres_user,
        password=settings.web_log_postgres_password,
    )


def initialize_database() -> None:
    with get_connection() as connection:
        for statement in _MIGRATION_STATEMENTS:
            connection.execute(statement)
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
    with get_web_log_connection() as connection:
        for statement in _WEB_LOG_SCHEMA_STATEMENTS:
            connection.execute(statement)


_IMAGE_GENERATION_FIELDS = (
    "id, user_id, prompt_id, client_id, status, prompt, negative_prompt, checkpoint, "
    "loras, cfg, steps, width, height, seed, file_path, storage_file_id, filename, "
    "subfolder, image_type, view_count, is_favorite, created_at, completed_at, elapsed_seconds, "
    "source_generation_id, is_edited, size_bytes"
)


def create_image_generation(
    *,
    user_id: uuid.UUID,
    prompt_id: str,
    client_id: str,
    prompt: str,
    negative_prompt: str,
    checkpoint: str,
    loras: list[dict[str, Any]],
    cfg: float,
    steps: int,
    width: int,
    height: int,
    seed: int,
) -> tuple[uuid.UUID, datetime]:
    generation_id = uuid.uuid4()
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO image_generations
                (id, user_id, prompt_id, client_id, prompt, negative_prompt, checkpoint,
                 loras, cfg, steps, width, height, seed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                generation_id,
                user_id,
                prompt_id,
                client_id,
                prompt,
                negative_prompt,
                checkpoint,
                json.dumps(loras, ensure_ascii=False),
                cfg,
                steps,
                width,
                height,
                seed,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("image generation insert did not return a row")
    return row[0], row[1]


def create_image_edit(
    *,
    user_id: uuid.UUID,
    source_generation_id: uuid.UUID,
    storage_file_id: str,
    filename: str,
    width: int,
    height: int,
    elapsed_seconds: float,
    size_bytes: int = 0,
) -> uuid.UUID | None:
    generation_id = uuid.uuid4()
    prompt_id = f"edit-image-{generation_id.hex}"
    client_id = f"edit-{generation_id.hex}"
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO image_generations
                (id, user_id, prompt_id, client_id, status, prompt, negative_prompt, checkpoint,
                 loras, cfg, steps, width, height, seed, storage_file_id, filename, subfolder,
                 image_type, completed_at, elapsed_seconds, source_generation_id, is_edited, size_bytes)
            SELECT %s, user_id, %s, %s, 'completed', prompt, negative_prompt, checkpoint,
                   loras, cfg, steps, %s, %s, seed, %s, %s, '', 'output', CURRENT_TIMESTAMP,
                   %s, %s, TRUE, %s
            FROM image_generations
            WHERE id = %s AND user_id = %s AND status = 'completed'
            RETURNING id
            """,
            (
                generation_id,
                prompt_id,
                client_id,
                width,
                height,
                storage_file_id,
                filename,
                elapsed_seconds,
                source_generation_id,
                size_bytes,
                source_generation_id,
                user_id,
            ),
        ).fetchone()
    return row[0] if row is not None else None


def get_image_generation(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE prompt_id = %s AND user_id = %s",
            (prompt_id, user_id),
        ).fetchone()
    return _image_generation_row(row)


def list_active_image_generations(user_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    filters = ["status IN ('queued', 'processing')"]
    parameters: list[Any] = []
    if user_id is not None:
        filters.append("user_id = %s")
        parameters.append(user_id)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE {' AND '.join(filters)} ORDER BY created_at",
            parameters,
        ).fetchall()
    return [generation for row in rows if (generation := _image_generation_row(row)) is not None]


def get_image_generation_by_id(generation_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE id = %s AND user_id = %s",
            (generation_id, user_id),
        ).fetchone()
    return _image_generation_row(row)


def get_image_generations_by_ids(
    generation_ids: list[uuid.UUID], user_id: uuid.UUID
) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE id = ANY(%s) AND user_id = %s",
            (generation_ids, user_id),
        ).fetchall()
    return [generation for row in rows if (generation := _image_generation_row(row)) is not None]


def increment_image_generation_view_count(generation_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            UPDATE image_generations
            SET view_count = view_count + 1
            WHERE id = %s AND user_id = %s
            RETURNING {_IMAGE_GENERATION_FIELDS}
            """,
            (generation_id, user_id),
        ).fetchone()
    return _image_generation_row(row)


def update_image_favorite(
    generation_id: uuid.UUID, user_id: uuid.UUID, is_favorite: bool
) -> bool | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            UPDATE image_generations
            SET is_favorite = %s
            WHERE id = %s AND user_id = %s
            RETURNING is_favorite
            """,
            (is_favorite, generation_id, user_id),
        ).fetchone()
    return bool(row[0]) if row is not None else None


def list_image_generations(
    user_id: uuid.UUID,
    *,
    search: str = "",
    sort: str = "latest",
    favorites_only: bool = False,
    page: int = 1,
) -> tuple[list[dict[str, Any]], int, int]:
    order_by = {
        "latest": "created_at DESC, id DESC",
        "oldest": "created_at ASC, id ASC",
        "most_viewed": "view_count DESC, created_at DESC, id DESC",
    }.get(sort, "created_at DESC, id DESC")
    filters = ["user_id = %s"]
    parameters: list[Any] = [user_id]
    normalized_search = search.strip()
    if normalized_search:
        filters.append("prompt ILIKE %s")
        parameters.append(f"%{normalized_search}%")
    if favorites_only:
        filters.append("is_favorite = TRUE")
    where_clause = " AND ".join(filters)
    page_size = 10
    offset = (page - 1) * page_size
    with get_connection() as connection:
        count_row = connection.execute(
            f"SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'completed') FROM image_generations WHERE {where_clause}",
            parameters,
        ).fetchone()
        rows = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE {where_clause} ORDER BY {order_by} LIMIT %s OFFSET %s",
            [*parameters, page_size, offset],
        ).fetchall()
    return (
        [generation for row in rows if (generation := _image_generation_row(row)) is not None],
        int(count_row[0]),
        int(count_row[1]),
    )


def delete_image_generation(generation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "DELETE FROM image_generations WHERE id = %s AND user_id = %s RETURNING id",
            (generation_id, user_id),
        ).fetchone()
    return row is not None


def delete_image_generations(generation_ids: list[uuid.UUID], user_id: uuid.UUID) -> int:
    with get_connection() as connection:
        rows = connection.execute(
            "DELETE FROM image_generations WHERE id = ANY(%s) AND user_id = %s RETURNING id",
            (generation_ids, user_id),
        ).fetchall()
    return len(rows)


_MEDIA_FIELDS = "id, user_id, storage_file_id, filename, content_type, media_kind, size, source_type, created_at"
_REUSABLE_MEDIA_FIELDS = "file_id, filename, content_type, media_kind, source_type, created_at, size"
_MODEL_DOWNLOAD_FIELDS = "id, user_id, version_id, model_type, file_index, filename, target_path, status, downloaded_bytes, total_bytes, error_message, created_at, completed_at"


def create_media_asset(
    *,
    user_id: uuid.UUID,
    storage_file_id: str,
    filename: str,
    content_type: str,
    media_kind: str,
    size: int,
    source_type: str = "generation_input",
) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            INSERT INTO media_assets
                (id, user_id, storage_file_id, filename, content_type, media_kind, size, source_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (storage_file_id) DO UPDATE
            SET source_type = 'generation_input'
            WHERE media_assets.user_id = EXCLUDED.user_id
            RETURNING {_MEDIA_FIELDS}
            """,
            (uuid.uuid4(), user_id, storage_file_id, filename, content_type, media_kind, size, source_type),
        ).fetchone()
    return dict(zip(_MEDIA_FIELDS.split(", "), row, strict=True))


def has_media_asset(storage_file_id: str, user_id: uuid.UUID) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM media_assets WHERE storage_file_id = %s AND user_id = %s",
            (storage_file_id, user_id),
        ).fetchone()
    return row is not None


def list_reusable_media(
    user_id: uuid.UUID,
    *,
    search: str = "",
    sort: str = "latest",
    include_generated: bool = False,
    media_kind: str | None = None,
    source_type: str | None = None,
    page: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    order_by = {
        "latest": "created_at DESC, file_id",
        "oldest": "created_at ASC, file_id",
        "name": "LOWER(filename) ASC, created_at DESC, file_id",
    }.get(sort, "created_at DESC, file_id")
    sources = [
        """
        SELECT storage_file_id AS file_id, filename, content_type, media_kind,
               source_type, created_at, size, user_id
        FROM media_assets
        WHERE NOT EXISTS (
            SELECT 1 FROM image_generations
            WHERE image_generations.storage_file_id = media_assets.storage_file_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM video_generations
            WHERE video_generations.storage_file_id = media_assets.storage_file_id
        )
        """
    ]
    if include_generated:
        sources.extend(
            (
                """
                SELECT storage_file_id AS file_id, COALESCE(filename, 'generated-image.png'),
                       'image/png', 'image', 'image_generation', created_at, size_bytes, user_id
                FROM image_generations
                WHERE storage_file_id IS NOT NULL
                """,
                """
                SELECT storage_file_id AS file_id, COALESCE(filename, 'generated-video.mp4'),
                       'video/mp4', 'video', 'video_generation', created_at, size_bytes, user_id
                FROM video_generations
                WHERE storage_file_id IS NOT NULL
                """,
            )
        )
    filters = ["user_id = %s"]
    parameters: list[Any] = [user_id]
    if search.strip():
        filters.append("filename ILIKE %s")
        parameters.append(f"%{search.strip()}%")
    if media_kind:
        filters.append("media_kind = %s")
        parameters.append(media_kind)
    if source_type == "uploaded":
        filters.append("source_type NOT IN ('image_generation', 'video_generation')")
    elif source_type == "generated":
        filters.append("source_type IN ('image_generation', 'video_generation')")
    page_size = 10
    offset = (page - 1) * page_size
    query_from = f"FROM ({' UNION ALL '.join(sources)}) AS assets WHERE {' AND '.join(filters)}"
    with get_connection() as connection:
        count_row = connection.execute(f"SELECT COUNT(*) {query_from}", parameters).fetchone()
        rows = connection.execute(
            f"SELECT {_REUSABLE_MEDIA_FIELDS} {query_from} ORDER BY {order_by} LIMIT %s OFFSET %s",
            [*parameters, page_size, offset],
        ).fetchall()
    return [dict(zip(_REUSABLE_MEDIA_FIELDS.split(", "), row, strict=True)) for row in rows], int(count_row[0])


def create_model_download(
    *,
    user_id: uuid.UUID,
    version_id: int,
    model_type: str,
    file_index: int,
    filename: str,
    target_path: str,
) -> dict[str, Any] | None:
    download_id = uuid.uuid4()
    try:
        with get_connection() as connection:
            row = connection.execute(
                f"""
                INSERT INTO model_downloads (id, user_id, version_id, model_type, file_index, filename, target_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING {_MODEL_DOWNLOAD_FIELDS}
                """,
                (download_id, user_id, version_id, model_type, file_index, filename, target_path),
            ).fetchone()
    except psycopg.Error as exc:
        if getattr(exc, "sqlstate", None) == "23505":
            return None
        raise
    return dict(zip(_MODEL_DOWNLOAD_FIELDS.split(", "), row, strict=True))


def get_model_download(download_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_MODEL_DOWNLOAD_FIELDS} FROM model_downloads WHERE id = %s AND user_id = %s",
            (download_id, user_id),
        ).fetchone()
    return None if row is None else dict(zip(_MODEL_DOWNLOAD_FIELDS.split(", "), row, strict=True))


def list_model_downloads(user_id: uuid.UUID, limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_MODEL_DOWNLOAD_FIELDS} FROM model_downloads WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit),
        ).fetchall()
    return [dict(zip(_MODEL_DOWNLOAD_FIELDS.split(", "), row, strict=True)) for row in rows]


def reset_model_downloads() -> None:
    with get_connection() as connection:
        connection.execute("UPDATE model_downloads SET status = 'queued' WHERE status = 'downloading'")


def claim_model_download() -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            UPDATE model_downloads
            SET status = 'downloading', error_message = NULL
            WHERE id = (
                SELECT id FROM model_downloads
                WHERE status = 'queued'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING {_MODEL_DOWNLOAD_FIELDS}
            """
        ).fetchone()
    return None if row is None else dict(zip(_MODEL_DOWNLOAD_FIELDS.split(", "), row, strict=True))


def update_model_download_progress(download_id: uuid.UUID, downloaded_bytes: int, total_bytes: int | None) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "UPDATE model_downloads SET downloaded_bytes = %s, total_bytes = %s WHERE id = %s AND status = 'downloading' RETURNING id",
            (downloaded_bytes, total_bytes, download_id),
        ).fetchone()
    return row is not None


def complete_model_download(download_id: uuid.UUID, downloaded_bytes: int, total_bytes: int | None) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            """
            UPDATE model_downloads
            SET status = 'completed', downloaded_bytes = %s, total_bytes = %s,
                error_message = NULL, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'downloading'
            RETURNING id
            """,
            (downloaded_bytes, total_bytes, download_id),
        ).fetchone()
    return row is not None


def is_model_download_active(download_id: uuid.UUID) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM model_downloads WHERE id = %s AND status = 'downloading'",
            (download_id,),
        ).fetchone()
    return row is not None


def fail_model_download(download_id: uuid.UUID, error_message: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE model_downloads SET status = 'failed', error_message = %s WHERE id = %s AND status = 'downloading'",
            (error_message[:1000], download_id),
        )


def cancel_model_download(download_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            UPDATE model_downloads
            SET status = 'cancelled', error_message = '다운로드가 중단되었습니다.'
            WHERE id = %s AND user_id = %s AND status IN ('queued', 'downloading')
            RETURNING {_MODEL_DOWNLOAD_FIELDS}
            """,
            (download_id, user_id),
        ).fetchone()
    return None if row is None else dict(zip(_MODEL_DOWNLOAD_FIELDS.split(", "), row, strict=True))


def retry_model_download(download_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            UPDATE model_downloads
            SET status = 'queued', downloaded_bytes = 0, total_bytes = NULL,
                error_message = NULL, completed_at = NULL
            WHERE id = %s AND user_id = %s AND status IN ('failed', 'cancelled')
            RETURNING {_MODEL_DOWNLOAD_FIELDS}
            """,
            (download_id, user_id),
        ).fetchone()
    return None if row is None else dict(zip(_MODEL_DOWNLOAD_FIELDS.split(", "), row, strict=True))


def get_media_asset(file_id: str, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_MEDIA_FIELDS} FROM media_assets WHERE storage_file_id = %s AND user_id = %s",
            (file_id, user_id),
        ).fetchone()
    if row is None:
        return None
    return dict(zip(_MEDIA_FIELDS.split(", "), row, strict=True))


def delete_media_asset(file_id: str, user_id: uuid.UUID) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "DELETE FROM media_assets WHERE storage_file_id = %s AND user_id = %s RETURNING storage_file_id",
            (file_id, user_id),
        ).fetchone()
    return row is not None


def get_reusable_media(file_id: str, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT {_REUSABLE_MEDIA_FIELDS} FROM (
                SELECT storage_file_id AS file_id, filename, content_type, media_kind,
                       source_type, created_at, size, user_id
                FROM media_assets
                UNION ALL
                SELECT storage_file_id AS file_id, COALESCE(filename, 'generated-image.png'),
                       'image/png', 'image', 'image_generation', created_at, size_bytes, user_id
                FROM image_generations
                WHERE storage_file_id IS NOT NULL
                UNION ALL
                SELECT storage_file_id AS file_id, COALESCE(filename, 'generated-video.mp4'),
                       'video/mp4', 'video', 'video_generation', created_at, size_bytes, user_id
                FROM video_generations
                WHERE storage_file_id IS NOT NULL
            ) AS assets
            WHERE file_id = %s AND user_id = %s
            LIMIT 1
            """,
            (file_id, user_id),
        ).fetchone()
    if row is None:
        return None
    return dict(zip(_REUSABLE_MEDIA_FIELDS.split(", "), row, strict=True))


_VIDEO_FIELDS = (
    "id, user_id, prompt_id, client_id, mode, status, prompt, width, height, length, fps, seed, "
    "input_file_ids, storage_file_id, filename, subfolder, video_type, view_count, is_favorite, "
    "created_at, completed_at, elapsed_seconds, source_generation_id, is_edited, size_bytes"
)

def create_video_generation(
    *,
    user_id: uuid.UUID,
    prompt_id: str,
    client_id: str,
    mode: str,
    prompt: str,
    width: int,
    height: int,
    length: int,
    fps: float,
    seed: int,
    input_file_ids: list[str],
) -> tuple[uuid.UUID, datetime]:
    generation_id = uuid.uuid4()
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO video_generations
                (id, user_id, prompt_id, client_id, mode, prompt, width, height, length, fps, seed, input_file_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (
                generation_id,
                user_id,
                prompt_id,
                client_id,
                mode,
                prompt,
                width,
                height,
                length,
                fps,
                seed,
                json.dumps(input_file_ids),
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("video generation insert did not return a row")
    return row[0], row[1]


def create_video_edit(
    *,
    user_id: uuid.UUID,
    source_generation_id: uuid.UUID,
    storage_file_id: str,
    filename: str,
    width: int,
    height: int,
    length: int,
    elapsed_seconds: float,
    size_bytes: int = 0,
) -> uuid.UUID | None:
    generation_id = uuid.uuid4()
    prompt_id = f"edit-video-{generation_id.hex}"
    client_id = f"edit-{generation_id.hex}"
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO video_generations
                (id, user_id, prompt_id, client_id, mode, status, prompt, width, height, length,
                 fps, seed, input_file_ids, storage_file_id, filename, subfolder, video_type,
                 completed_at, elapsed_seconds, source_generation_id, is_edited, size_bytes)
            SELECT %s, user_id, %s, %s, mode, 'completed', prompt, %s, %s, %s,
                   fps, seed, input_file_ids, %s, %s, '', 'output', CURRENT_TIMESTAMP,
                   %s, %s, TRUE, %s
            FROM video_generations
            WHERE id = %s AND user_id = %s AND status = 'completed'
            RETURNING id
            """,
            (
                generation_id,
                prompt_id,
                client_id,
                width,
                height,
                length,
                storage_file_id,
                filename,
                elapsed_seconds,
                source_generation_id,
                size_bytes,
                source_generation_id,
                user_id,
            ),
        ).fetchone()
    return row[0] if row is not None else None


def get_video_generation(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_VIDEO_FIELDS} FROM video_generations WHERE prompt_id = %s AND user_id = %s",
            (prompt_id, user_id),
        ).fetchone()
    return _video_generation_row(row)


def list_active_video_generations(user_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    filters = ["status IN ('queued', 'processing')"]
    parameters: list[Any] = []
    if user_id is not None:
        filters.append("user_id = %s")
        parameters.append(user_id)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_VIDEO_FIELDS} FROM video_generations WHERE {' AND '.join(filters)} ORDER BY created_at",
            parameters,
        ).fetchall()
    return [generation for row in rows if (generation := _video_generation_row(row)) is not None]


def get_video_generation_by_id(generation_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_VIDEO_FIELDS} FROM video_generations WHERE id = %s AND user_id = %s",
            (generation_id, user_id),
        ).fetchone()
    return _video_generation_row(row)


def increment_video_generation_view_count(generation_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            UPDATE video_generations
            SET view_count = view_count + 1
            WHERE id = %s AND user_id = %s
            RETURNING {_VIDEO_FIELDS}
            """,
            (generation_id, user_id),
        ).fetchone()
    return _video_generation_row(row)


def update_video_favorite(generation_id: uuid.UUID, user_id: uuid.UUID, is_favorite: bool) -> bool | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            UPDATE video_generations
            SET is_favorite = %s
            WHERE id = %s AND user_id = %s
            RETURNING is_favorite
            """,
            (is_favorite, generation_id, user_id),
        ).fetchone()
    return bool(row[0]) if row is not None else None


def list_video_generations(
    user_id: uuid.UUID,
    *,
    search: str = "",
    sort: str = "latest",
    favorites_only: bool = False,
    page: int = 1,
) -> tuple[list[dict[str, Any]], int, int]:
    order_by = {
        "latest": "created_at DESC, id DESC",
        "oldest": "created_at ASC, id ASC",
        "most_viewed": "view_count DESC, created_at DESC, id DESC",
    }.get(sort, "created_at DESC, id DESC")
    filters = ["user_id = %s"]
    parameters: list[Any] = [user_id]
    if search.strip():
        filters.append("prompt ILIKE %s")
        parameters.append(f"%{search.strip()}%")
    if favorites_only:
        filters.append("is_favorite = TRUE")
    page_size = 10
    offset = (page - 1) * page_size
    where_clause = " AND ".join(filters)
    with get_connection() as connection:
        count_row = connection.execute(
            f"SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'completed') FROM video_generations WHERE {where_clause}",
            parameters,
        ).fetchone()
        rows = connection.execute(
            f"SELECT {_VIDEO_FIELDS} FROM video_generations WHERE {where_clause} ORDER BY {order_by} LIMIT %s OFFSET %s",
            [*parameters, page_size, offset],
        ).fetchall()
    return (
        [dict(zip(_VIDEO_FIELDS.split(", "), row, strict=True)) for row in rows],
        int(count_row[0]),
        int(count_row[1]),
    )


def delete_video_generation(generation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "DELETE FROM video_generations WHERE id = %s AND user_id = %s RETURNING id",
            (generation_id, user_id),
        ).fetchone()
    return row is not None


def update_video_generation_status(
    *,
    prompt_id: str,
    user_id: uuid.UUID,
    status: str,
    storage_file_id: str | None = None,
    filename: str | None = None,
    subfolder: str = "",
    video_type: str = "output",
    size_bytes: int | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE video_generations
            SET status = %s,
                storage_file_id = COALESCE(%s, storage_file_id),
                filename = COALESCE(%s, filename),
                subfolder = COALESCE(%s::varchar, subfolder),
                video_type = COALESCE(%s::varchar, video_type),
                size_bytes = COALESCE(%s, size_bytes),
                completed_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE completed_at END,
                elapsed_seconds = GREATEST(0, EXTRACT(EPOCH FROM (
                    CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE CURRENT_TIMESTAMP END - created_at
                )))
            WHERE prompt_id = %s AND user_id = %s
            """,
            (
                status,
                storage_file_id,
                filename,
                subfolder if filename is not None else None,
                video_type if filename is not None else None,
                size_bytes,
                status,
                status,
                prompt_id,
                user_id,
            ),
        )


def _video_generation_row(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(zip(_VIDEO_FIELDS.split(", "), row, strict=True))


_PRESET_FIELDS = "id, user_id, type, name, values, is_default, created_at, updated_at"


def create_preset(
    *, user_id: uuid.UUID, preset_type: str, name: str, values: dict[str, Any], is_default: bool = False
) -> dict[str, Any]:
    with get_connection() as connection:
        if is_default:
            connection.execute(
                "UPDATE presets SET is_default = FALSE WHERE user_id = %s AND type = %s",
                (user_id, preset_type),
            )
        row = connection.execute(
            f"""
            INSERT INTO presets (id, user_id, type, name, values, is_default)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            RETURNING {_PRESET_FIELDS}
            """,
            (uuid.uuid4(), user_id, preset_type, name, json.dumps(values, ensure_ascii=False), is_default),
        ).fetchone()
    return _preset_row(row)


def list_presets(*, user_id: uuid.UUID, preset_type: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_PRESET_FIELDS} FROM presets WHERE user_id = %s AND type = %s ORDER BY updated_at DESC, name",
            (user_id, preset_type),
        ).fetchall()
    return [_preset_row(row) for row in rows]


def update_preset(
    *,
    preset_id: uuid.UUID,
    user_id: uuid.UUID,
    preset_type: str,
    name: str,
    values: dict[str, Any],
    is_default: bool | None = None,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        target = connection.execute(
            "SELECT id FROM presets WHERE id = %s AND user_id = %s AND type = %s FOR UPDATE",
            (preset_id, user_id, preset_type),
        ).fetchone()
        if target is None:
            return None
        if is_default is True:
            connection.execute(
                "UPDATE presets SET is_default = FALSE WHERE user_id = %s AND type = %s AND id <> %s",
                (user_id, preset_type, preset_id),
            )
        row = connection.execute(
            f"""
            UPDATE presets
            SET name = %s,
                values = %s::jsonb,
                is_default = COALESCE(%s, is_default),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s AND type = %s
            RETURNING {_PRESET_FIELDS}
            """,
            (name, json.dumps(values, ensure_ascii=False), is_default, preset_id, user_id, preset_type),
        ).fetchone()
    return _preset_row(row) if row is not None else None


def delete_preset(*, preset_id: uuid.UUID, user_id: uuid.UUID, preset_type: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "DELETE FROM presets WHERE id = %s AND user_id = %s AND type = %s RETURNING id",
            (preset_id, user_id, preset_type),
        ).fetchone()
    return row is not None


def _preset_row(row: tuple[Any, ...] | None) -> dict[str, Any]:
    if row is None:
        raise RuntimeError("프리셋 저장 결과가 없습니다.")
    return dict(zip(_PRESET_FIELDS.split(", "), row, strict=True))


def update_image_generation_status(
    *,
    prompt_id: str,
    user_id: uuid.UUID,
    status: str,
    file_path: str | None = None,
    storage_file_id: str | None = None,
    filename: str | None = None,
    subfolder: str = "",
    image_type: str = "output",
    size_bytes: int | None = None,
) -> None:
    with get_connection() as connection:
        if file_path is None:
            connection.execute(
                """
                UPDATE image_generations
                SET status = %s,
                    completed_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE completed_at END,
                    elapsed_seconds = GREATEST(0, EXTRACT(EPOCH FROM (
                        CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE CURRENT_TIMESTAMP END - created_at
                    )))
                WHERE prompt_id = %s AND user_id = %s
                """,
                (status, status, status, prompt_id, user_id),
            )
        else:
            connection.execute(
                """
                UPDATE image_generations
                SET status = %s,
                    file_path = %s,
                    storage_file_id = COALESCE(%s, storage_file_id),
                    filename = %s,
                    subfolder = %s,
                    image_type = %s,
                    size_bytes = COALESCE(%s, size_bytes),
                    completed_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE completed_at END,
                    elapsed_seconds = GREATEST(0, EXTRACT(EPOCH FROM (
                        CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE CURRENT_TIMESTAMP END - created_at
                    )))
                WHERE prompt_id = %s AND user_id = %s
                """,
                (status, file_path, storage_file_id, filename, subfolder, image_type, size_bytes, status, status, prompt_id, user_id),
            )


def _image_generation_row(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(zip(_IMAGE_GENERATION_FIELDS.split(", "), row, strict=True))


def generation_elapsed_seconds(generation: dict[str, Any]) -> float:
    elapsed = max(0.0, float(generation.get("elapsed_seconds") or 0))
    if generation.get("status") in {"queued", "processing"}:
        created_at = generation.get("created_at")
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            elapsed = max(elapsed, (datetime.now(timezone.utc) - created_at).total_seconds())
    return round(elapsed, 3)


def record_auth_event(
    *,
    event_type: str,
    username: str | None,
    success: bool,
    failure_reason: str | None,
    client_ip: str | None,
    user_agent: str | None,
    user_id: Any = None,
) -> None:
    _record(
        """
        INSERT INTO auth_history
            (event_type, username, success, failure_reason, client_ip, user_agent, user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (event_type, username, success, failure_reason, client_ip, user_agent, user_id),
    )


def record_api_call(
    *,
    method: str,
    path: str,
    status_code: int,
    client_ip: str | None,
    user_agent: str | None,
    user_id: Any = None,
) -> None:
    _record(
        """
        INSERT INTO api_audit_logs
            (method, path, status_code, client_ip, user_agent, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (method, path, status_code, client_ip, user_agent, user_id),
    )


def record_api_error(
    *,
    method: str,
    path: str,
    status_code: int,
    error_type: str,
    error_message: str,
    client_ip: str | None,
    user_agent: str | None,
    user_id: Any = None,
) -> None:
    _record(
        """
        INSERT INTO api_error_logs
            (method, path, status_code, error_type, error_message, client_ip, user_agent, user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            method,
            path,
            status_code,
            error_type,
            error_message[:1000],
            client_ip,
            user_agent,
            user_id,
        ),
    )


def record_web_event(
    *,
    event_type: str,
    page_path: str,
    from_path: str | None,
    target_type: str,
    target_id: str | None,
    target_label: str | None,
    target_href: str | None,
    client_ip: str | None,
    user_agent: str | None,
    user_id: Any = None,
) -> None:
    try:
        with get_web_log_connection() as connection:
            connection.execute(
                """
                INSERT INTO web_event_logs
                    (event_type, page_path, from_path, target_type, target_id, target_label,
                     target_href, client_ip, user_agent, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_type,
                    page_path,
                    from_path,
                    target_type,
                    target_id,
                    target_label,
                    target_href,
                    client_ip,
                    user_agent,
                    user_id,
                ),
            )
    except Exception:
        # Logging must not replace the original API response or exception.
        return


def _record(statement: str, parameters: Iterable[Any]) -> None:
    try:
        with get_connection() as connection:
            connection.execute(statement, tuple(parameters))
    except Exception:
        # Logging must not replace the original API response or exception.
        return
