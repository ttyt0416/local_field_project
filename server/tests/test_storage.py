import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from urllib.request import Request

from app import storage


class _Response:
    def __init__(self, payload: dict | None = None):
        self._body = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


class StorageClientTest(unittest.TestCase):
    def test_upload_file_sends_owner_and_authentication(self) -> None:
        with (
            patch(
                "app.storage.settings",
                replace(storage.settings, storage_url="https://storage.example", storage_api_token="service-token"),
            ),
            patch("app.storage.urlopen", return_value=_Response({"id": "file-id"})) as open_url,
        ):
            file_id = storage.upload_file(content=b"image", media_type="image/png", owner_id="user-id")

        self.assertEqual(file_id, "file-id")
        request = open_url.call_args.args[0]
        self.assertIsInstance(request, Request)
        self.assertEqual(request.full_url, "https://storage.example/files")
        self.assertEqual(request.get_header("Authorization"), "Bearer service-token")
        self.assertEqual(request.get_header("Content-type"), "image/png")
        self.assertEqual(request.get_header("X-owner-id"), "user-id")
        self.assertEqual(request.data, b"image")

    def test_read_url_uses_file_id_and_expiry(self) -> None:
        with (
            patch(
                "app.storage.settings",
                replace(storage.settings, storage_url="https://storage.example/", storage_api_token="service-token"),
            ),
            patch("app.storage.urlopen", return_value=_Response({"url": "https://cdn.example/file"})) as open_url,
        ):
            url = storage.read_url(file_id="file/id", owner_id="user-id", expires_in=60)

        self.assertEqual(url, "https://cdn.example/file")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://storage.example/files/file%2Fid/url?expires_in=60")
        self.assertEqual(request.get_header("Authorization"), "Bearer service-token")
        self.assertEqual(request.get_header("X-owner-id"), "user-id")

    def test_delete_file_accepts_no_content(self) -> None:
        with (
            patch(
                "app.storage.settings",
                replace(storage.settings, storage_url="https://storage.example/", storage_api_token="service-token"),
            ),
            patch("app.storage.urlopen", return_value=_Response()) as open_url,
        ):
            storage.delete_file(file_id="file/id", owner_id="user-id")

        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://storage.example/files/file%2Fid")
        self.assertEqual(request.get_header("Authorization"), "Bearer service-token")
        self.assertEqual(request.get_header("X-owner-id"), "user-id")


if __name__ == "__main__":
    unittest.main()
