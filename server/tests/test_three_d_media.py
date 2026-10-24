import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4
from types import SimpleNamespace

from fastapi import FastAPI

from app import three_d, vault
from app.auth import UserResponse, current_user
from app.storage import StorageError


class ThreeDMediaTest(unittest.TestCase):
    def setUp(self):
        self.user = UserResponse(id=uuid4(), username="model-test")
        self.generation_id = uuid4()
        self.row = {
            "id": self.generation_id, "prompt_id": "prompt", "client_id": "client",
            "status": "completed", "stage": "completed", "generation_mode": "mesh",
            "storage_file_id": "output-file", "source_file_id": None,
            "filename": "model.glb", "preset": "standard", "seed": 1,
            "created_at": datetime.now(timezone.utc), "completed_at": None,
            "elapsed_seconds": 1, "view_count": 0, "is_favorite": False,
            "size_bytes": 16,
        }
        app = FastAPI()
        app.include_router(vault.router)
        app.dependency_overrides[current_user] = lambda: self.user
        self.app = app
        self.path = f"/vault/3d/{self.generation_id}/model"

    def get(self, path):
        messages = []
        path, _, query = path.partition("?")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(self.app({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": path,
            "query_string": query.encode(), "root_path": "", "headers": [],
            "server": ("test", 80), "client": ("127.0.0.1", 1),
        }, receive, send))
        start = next(message for message in messages if message["type"] == "http.response.start")
        return SimpleNamespace(
            status_code=start["status"],
            headers={key.decode(): value.decode() for key, value in start["headers"]},
            content=b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body"),
        )

    def test_authenticated_response_contains_glb_without_redirect(self):
        with (
            patch.object(vault, "get_three_d_generation_by_id", return_value=self.row) as owned,
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "storage_download_file", return_value=(b"glTF-model", "application/octet-stream")) as download,
        ):
            response = self.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"glTF-model")
        self.assertEqual(response.headers["content-type"], "model/gltf-binary")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertNotIn("location", response.headers)
        owned.assert_called_once_with(self.generation_id, self.user.id)
        download.assert_called_once_with(file_id="output-file", owner_id=str(self.user.id))

    def test_inaccessible_generation_does_not_read_storage(self):
        with (
            patch.object(vault, "get_three_d_generation_by_id", return_value=None),
            patch.object(vault, "storage_download_file") as download,
        ):
            response = self.get(self.path)
        self.assertEqual(response.status_code, 404)
        download.assert_not_called()

    def test_unauthenticated_request_is_rejected_before_storage(self):
        self.app.dependency_overrides.clear()
        with patch.object(vault, "storage_download_file") as download:
            response = self.get(self.path)
        self.assertEqual(response.status_code, 401)
        download.assert_not_called()

    def test_mesh_source_and_unfinished_output_are_unavailable(self):
        for row, query in ((self.row, "?source=true"), ({**self.row, "status": "processing"}, "")):
            with (
                self.subTest(query=query),
                patch.object(vault, "get_three_d_generation_by_id", return_value=row),
                patch.object(vault, "storage_download_file") as download,
            ):
                response = self.get(self.path + query)
            self.assertEqual(response.status_code, 404)
            download.assert_not_called()

    def test_rigging_source_reads_the_owned_original_model(self):
        row = {**self.row, "generation_mode": "rigging", "source_file_id": "source-model"}
        with (
            patch.object(vault, "get_three_d_generation_by_id", return_value=row),
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "storage_download_file", return_value=(b"glTF-source", "model/gltf-binary")) as download,
        ):
            response = self.get(self.path + "?source=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"glTF-source")
        download.assert_called_once_with(file_id="source-model", owner_id=str(self.user.id))

    def test_storage_failure_is_reported(self):
        with (
            patch.object(vault, "get_three_d_generation_by_id", return_value=self.row),
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "storage_download_file", side_effect=StorageError("storage unavailable")),
        ):
            response = self.get(self.path)
        self.assertEqual(response.status_code, 503)

    def test_vault_and_generation_results_use_authenticated_model_path(self):
        for mode in ("mesh", "rigging"):
            row = {**self.row, "generation_mode": mode, "source_file_id": "source-file"}
            with (
                self.subTest(mode=mode),
                patch.object(vault, "storage_enabled", return_value=True),
                patch.object(vault, "storage_read_url", return_value="https://storage/source") as signed_url,
            ):
                summary = vault._three_d_summary(row, self.user.id)
                result = three_d._status_from_row(row, self.user.id, progress={"progress": 100})
            self.assertEqual(summary.model_url, self.path.lstrip("/"))
            self.assertEqual(result.model.url, summary.model_url)
            if mode == "rigging":
                self.assertEqual(summary.source_model_url, summary.model_url + "?source=true")
                self.assertIsNone(summary.source_image_url)
                signed_url.assert_not_called()
            else:
                self.assertEqual(summary.source_image_url, "https://storage/source")
