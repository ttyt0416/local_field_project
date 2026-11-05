from __future__ import annotations

from psycopg import Connection, sql


_CONTENT_TABLES = (
    "presets", "image_generations", "media_assets", "video_generations",
    "music_generations", "three_d_generations", "model_downloads", "saved_prompts",
)


def _columns(connection: Connection, table: str) -> set[str]:
    return {row[0] for row in connection.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s",
        (table,),
    ).fetchall()}


def migrate_shared_data(connection: Connection) -> None:
    legacy_accounts = bool(_columns(connection, "users"))
    connection.execute("CREATE TABLE IF NOT EXISTS storage_file_owners (file_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)")
    for table in _CONTENT_TABLES:
        columns = _columns(connection, table)
        if "user_id" not in columns:
            continue
        for column in ("storage_file_id", "source_file_id"):
            if column in columns:
                connection.execute(sql.SQL("""
                    INSERT INTO storage_file_owners (file_id, owner_id)
                    SELECT {column}, user_id::text FROM {table}
                    WHERE {column} IS NOT NULL AND {column} <> ''
                    ON CONFLICT (file_id) DO NOTHING
                """).format(column=sql.Identifier(column), table=sql.Identifier(table)))
        for column in ("input_file_ids", "segment_file_ids", "reference_image_file_ids"):
            if column in columns:
                connection.execute(sql.SQL("""
                    INSERT INTO storage_file_owners (file_id, owner_id)
                    SELECT file_id, user_id::text FROM {table}, jsonb_array_elements_text({column}) AS file_id
                    WHERE file_id <> '' ON CONFLICT (file_id) DO NOTHING
                """).format(column=sql.Identifier(column), table=sql.Identifier(table)))
        if "reference_images" in columns:
            connection.execute(sql.SQL("""
                INSERT INTO storage_file_owners (file_id, owner_id)
                SELECT item->>'file_id', user_id::text FROM {table}, jsonb_array_elements(reference_images) AS item
                WHERE item->>'file_id' IS NOT NULL AND item->>'file_id' <> ''
                ON CONFLICT (file_id) DO NOTHING
            """).format(table=sql.Identifier(table)))
        if table == "presets":
            connection.execute("""
                UPDATE presets SET is_default = FALSE WHERE id IN (
                    SELECT id FROM (
                        SELECT id, row_number() OVER (PARTITION BY type ORDER BY updated_at DESC, id) AS rank
                        FROM presets WHERE is_default
                    ) AS defaults WHERE rank > 1
                )
            """)
        if table == "model_downloads":
            connection.execute("""
                UPDATE model_downloads SET status = 'cancelled', error_message = '공용 대기열의 중복 다운로드를 정리했습니다.'
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id, row_number() OVER (
                            PARTITION BY provider, version_id, model_type, file_index,
                                COALESCE(source_repo, ''), COALESCE(source_revision, ''), COALESCE(source_filename, '')
                            ORDER BY created_at, id
                        ) AS rank FROM model_downloads WHERE status IN ('queued', 'downloading')
                    ) AS downloads WHERE rank > 1
                )
            """)
        connection.execute(sql.SQL("ALTER TABLE {} DROP COLUMN user_id").format(sql.Identifier(table)))
    if "user_id" in _columns(connection, "download_tokens"):
        from .download_tokens import decrypt_token, encrypt_token
        rows = connection.execute("""
            SELECT DISTINCT ON (provider) provider, encrypted_token, updated_at
            FROM download_tokens ORDER BY provider, updated_at DESC, user_id
        """).fetchall()
        tokens = [(provider, encrypt_token(provider, decrypt_token(provider, encrypted)), updated_at)
                  for provider, encrypted, updated_at in rows]
        connection.execute("DELETE FROM download_tokens")
        connection.execute("ALTER TABLE download_tokens DROP COLUMN user_id")
        connection.execute("ALTER TABLE download_tokens ADD PRIMARY KEY (provider)")
        for token in tokens:
            connection.execute("INSERT INTO download_tokens (provider, encrypted_token, updated_at) VALUES (%s, %s, %s)", token)
    for table in ("api_audit_logs", "api_error_logs"):
        columns = _columns(connection, table)
        if legacy_accounts and "path" in columns:
            connection.execute(sql.SQL("DELETE FROM {} WHERE path ~ '^/?auth(/|$)'").format(sql.Identifier(table)))
        if "user_id" in columns:
            connection.execute(sql.SQL("ALTER TABLE {} DROP COLUMN user_id").format(sql.Identifier(table)))
    migrate_web_logs(connection)
    if _columns(connection, "auth_history"):
        connection.execute("DROP TABLE auth_history")
    if legacy_accounts:
        connection.execute("DROP TABLE users")


def migrate_web_logs(connection: Connection) -> None:
    if "user_id" in _columns(connection, "web_event_logs"):
        connection.execute("DELETE FROM web_event_logs WHERE page_path ~ '^/(login|signup|register)([/?#]|$)' OR target_href ~ '^/(login|signup|register)([/?#]|$)'")
        connection.execute("ALTER TABLE web_event_logs DROP COLUMN user_id")
