from collections.abc import Iterable
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
)


_SCHEMA_STATEMENTS: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector",
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
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS image_generations_user_id_idx ON image_generations(user_id)
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
    "subfolder, image_type, created_at, completed_at"
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
) -> uuid.UUID:
    generation_id = uuid.uuid4()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO image_generations
                (id, user_id, prompt_id, client_id, prompt, negative_prompt, checkpoint,
                 loras, cfg, steps, width, height, seed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
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
        )
    return generation_id


def get_image_generation(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE prompt_id = %s AND user_id = %s",
            (prompt_id, user_id),
        ).fetchone()
    return _image_generation_row(row)


def get_image_generation_by_id(generation_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE id = %s AND user_id = %s",
            (generation_id, user_id),
        ).fetchone()
    return _image_generation_row(row)


def list_image_generations(user_id: uuid.UUID) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_IMAGE_GENERATION_FIELDS} FROM image_generations WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [generation for row in rows if (generation := _image_generation_row(row)) is not None]


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
) -> None:
    with get_connection() as connection:
        if file_path is None:
            connection.execute(
                """
                UPDATE image_generations
                SET status = %s,
                    completed_at = CASE WHEN %s IN ('completed', 'failed') THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE prompt_id = %s AND user_id = %s
                """,
                (status, status, prompt_id, user_id),
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
                    completed_at = CURRENT_TIMESTAMP
                WHERE prompt_id = %s AND user_id = %s
                """,
                (status, file_path, storage_file_id, filename, subfolder, image_type, prompt_id, user_id),
            )


def _image_generation_row(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(zip(_IMAGE_GENERATION_FIELDS.split(", "), row, strict=True))


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
