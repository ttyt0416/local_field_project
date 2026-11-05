from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import replace
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from psycopg import sql

from app import accountless, audit, database, download_tokens, main, model_downloads
from app.configs.constants import settings


def request(path: str, method: str = "GET", body: bytes = b"") -> tuple[int, bytes]:
    messages = []
    path, _, query = path.partition("?")
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    async def send(message):
        messages.append(message)
    asyncio.run(main.app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "query_string": query.encode(),
        "root_path": "", "headers": [(b"content-type", b"application/json")],
        "server": ("test", 80), "client": ("127.0.0.1", 1),
    }, receive, send))
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    return status, b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")


class PublicApiTest(unittest.TestCase):
    def test_download_status_works_without_authorization(self):
        with patch.object(model_downloads, "list_model_downloads", return_value=[]) as listing, patch.object(audit, "fire_and_forget"):
            status, body = request("/models/downloads?limit=100")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), [])
        listing.assert_called_once_with(100, active_only=False)

    def test_account_routes_and_security_parameters_are_removed(self):
        schema = main.app.openapi()
        self.assertNotIn("securitySchemes", schema.get("components", {}))
        for path, methods in schema["paths"].items():
            self.assertFalse(path.startswith("/auth"))
            for operation in methods.values():
                self.assertNotIn("security", operation)
                for parameter in operation.get("parameters", []):
                    self.assertNotIn(parameter["name"], {"user", "user_id", "credentials"})
        for path in ("/auth/login", "/auth/signup", "/auth/me"):
            with patch.object(audit, "fire_and_forget"):
                status, _ = request(path, "GET" if path.endswith("me") else "POST", b'{}')
            self.assertEqual(status, 404)


@unittest.skipUnless(os.getenv("LOCAL_FIELD_MIGRATION_TESTS") == "1", "Requires PostgreSQL; all changes roll back in an isolated schema")
class SharedDataMigrationTest(unittest.TestCase):
    def setUp(self):
        self.connection = database.get_connection()
        self.addCleanup(self.connection.close)
        self.addCleanup(self.connection.rollback)
        self.schema = "accountless_test_" + uuid4().hex
        self.connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.connection.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(self.schema)))
        self.config = patch.object(download_tokens, "settings", replace(settings, token_encryption_secret="synthetic-migration-secret"))
        self.config.start()
        self.addCleanup(self.config.stop)
        @contextmanager
        def borrowed(**kwargs):
            yield self.connection
        self.borrowed = borrowed

    def initialize(self):
        for statement in database._MIGRATION_STATEMENTS:
            self.connection.execute(statement)
        accountless.migrate_shared_data(self.connection)
        for statement in database._SCHEMA_STATEMENTS:
            self.connection.execute(statement)
        accountless.migrate_web_logs(self.connection)
        for statement in database._WEB_LOG_SCHEMA_STATEMENTS:
            self.connection.execute(statement)

    def test_fresh_schema_and_shared_queries_work_without_accounts(self):
        self.initialize()
        self.initialize()
        with patch.object(database, "get_connection", self.borrowed):
            asset = database.create_media_asset(storage_file_id="shared-file", filename="test.png", content_type="image/png", media_kind="image", size=4)
            self.assertEqual(database.get_media_asset("shared-file")["id"], asset["id"])
            self.assertEqual(database.get_storage_owner("shared-file"), "local-field")
            preset = database.create_preset(preset_type="t2i", name="Test", values={})
            self.assertEqual(database.list_presets(preset_type="t2i")[0]["id"], preset["id"])
            self.assertEqual(database.list_model_downloads(), [])
        columns = self.connection.execute("SELECT table_name FROM information_schema.columns WHERE table_schema = current_schema() AND column_name = 'user_id'").fetchall()
        self.assertEqual(columns, [])

    def test_legacy_accounts_are_deleted_and_content_tokens_and_storage_survive(self):
        self.initialize()
        conn = self.connection
        conn.execute("CREATE TABLE users (id UUID PRIMARY KEY, username TEXT, password_hash TEXT)")
        conn.execute("CREATE TABLE auth_history (id BIGSERIAL PRIMARY KEY, user_id UUID REFERENCES users(id))")
        owners = (uuid4(), uuid4())
        for owner in owners:
            conn.execute("INSERT INTO users VALUES (%s, 'old-account', 'old-password-hash')", (owner,))
        for table in accountless._CONTENT_TABLES:
            conn.execute(sql.SQL("ALTER TABLE {} ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE CASCADE").format(sql.Identifier(table)))
        conn.execute("DROP INDEX presets_one_default_per_type_idx")
        conn.execute("CREATE UNIQUE INDEX presets_one_default_per_user_type_idx ON presets(user_id, type) WHERE is_default")
        conn.execute("ALTER TABLE download_tokens DROP CONSTRAINT download_tokens_pkey")
        conn.execute("ALTER TABLE download_tokens ADD COLUMN user_id UUID REFERENCES users(id)")
        conn.execute("ALTER TABLE download_tokens ADD PRIMARY KEY (user_id, provider)")
        for owner, token, age in ((owners[0], "older-token", "2 hours"), (owners[1], "newer-token", "1 hour")):
            encrypted = download_tokens._cipher().encrypt(json.dumps({"user_id": str(owner), "provider": "civitai", "token": token}).encode()).decode()
            conn.execute("INSERT INTO download_tokens VALUES ('civitai', %s, now() - %s::interval, %s)", (encrypted, age, owner))
            conn.execute("INSERT INTO presets (id, type, name, is_default, user_id) VALUES (%s, 't2i', 'Legacy', TRUE, %s)", (uuid4(), owner))
        with patch.object(database, "get_connection", self.borrowed):
            database.create_media_asset(storage_file_id="legacy-file", filename="old.png", content_type="image/png", media_kind="image", size=4)
        conn.execute("UPDATE media_assets SET user_id = %s", (owners[0],))
        for table in ("api_audit_logs", "api_error_logs", "web_event_logs"):
            conn.execute(sql.SQL("ALTER TABLE {} ADD COLUMN user_id UUID").format(sql.Identifier(table)))
        conn.execute("INSERT INTO api_audit_logs (method, path, status_code, user_id) VALUES ('POST', '/auth/signup', 201, %s)", (owners[0],))
        conn.execute("INSERT INTO web_event_logs (event_type, page_path, target_type, user_id) VALUES ('click', '/login', 'button', %s)", (owners[0],))
        self.initialize()
        self.initialize()
        self.assertIsNone(conn.execute("SELECT to_regclass(%s)", (self.schema + '.users',)).fetchone()[0])
        self.assertIsNone(conn.execute("SELECT to_regclass(%s)", (self.schema + '.auth_history',)).fetchone()[0])
        self.assertEqual(conn.execute("SELECT count(*) FROM media_assets").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT count(*) FROM presets").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT count(*) FROM presets WHERE is_default").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT count(*) FROM api_audit_logs WHERE path LIKE '/auth/%'").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT count(*) FROM web_event_logs").fetchone()[0], 0)
        encrypted = conn.execute("SELECT encrypted_token FROM download_tokens WHERE provider = 'civitai'").fetchone()[0]
        self.assertEqual(download_tokens.decrypt_token("civitai", encrypted), "newer-token")
        self.assertNotIn("user_id", json.loads(download_tokens._cipher().decrypt(encrypted.encode())))
        with patch.object(database, "get_connection", self.borrowed):
            self.assertEqual(database.get_media_asset("legacy-file")["filename"], "old.png")
            self.assertEqual(database.get_storage_owner("legacy-file"), str(owners[0]))
