from collections.abc import Iterable
from typing import Any

import psycopg

from .configs.constants import settings


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
)


_SCHEMA_STATEMENTS: tuple[str, ...] = (
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


def get_connection() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


def initialize_database() -> None:
    with get_connection() as connection:
        for statement in _MIGRATION_STATEMENTS:
            connection.execute(statement)
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)


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


def _record(statement: str, parameters: Iterable[Any]) -> None:
    try:
        with get_connection() as connection:
            connection.execute(statement, tuple(parameters))
    except Exception:
        # Logging must not replace the original API response or exception.
        return
