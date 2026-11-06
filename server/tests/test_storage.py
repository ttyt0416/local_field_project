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


class _DownloadHeaders:
    def get_content_type(self) -> str:
        return "image/png"


class _DownloadResponse:
    headers = _DownloadHeaders()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b"image"


class StorageClientTest(unittest.TestCase):
    def setUp(self):
        audit = patch('app.database.record_api_call')
        self.record = audit.start()
        self.addCleanup(audit.stop)
        owner = patch("app.storage.get_storage_owner", return_value="legacy-storage-owner")
        owner.start()
        self.addCleanup(owner.stop)
        storage._read_url_cache.clear()

    def test_upload_file_sends_owner_and_authentication(self) -> None:
        with (
            patch(
                "app.storage.settings",
                replace(storage.settings, storage_url="https://storage.example", storage_api_token="service-token"),
            ),
            patch("app.storage.urlopen", return_value=_Response({"id": "file-id"})) as open_url,
        ):
            file_id = storage.upload_file(content=b"image", media_type="image/png")

        self.assertEqual(file_id, "file-id")
        request = open_url.call_args.args[0]
        self.assertIsInstance(request, Request)
        self.assertEqual(request.full_url, "https://storage.example/files")
        self.assertEqual(request.get_header("Authorization"), "Bearer service-token")
        self.assertEqual(request.get_header("Content-type"), "image/png")
        self.assertEqual(request.get_header("X-owner-id"), "local-field")
        self.assertEqual(request.data, b"image")

    def test_read_url_uses_file_id_and_expiry(self) -> None:
        with (
            patch(
                "app.storage.settings",
                replace(storage.settings, storage_url="https://storage.example/", storage_api_token="service-token"),
            ),
            patch("app.storage.urlopen", return_value=_Response({"url": "https://cdn.example/file"})) as open_url,
        ):
            url = storage.read_url(file_id="file/id", expires_in=60)
            cached_url = storage.read_url(file_id="file/id", expires_in=60)

        self.assertEqual(url, "https://cdn.example/file")
        self.assertEqual(cached_url, url)
        self.assertEqual(open_url.call_count, 1)
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://storage.example/files/file%2Fid/url?expires_in=60")
        self.assertEqual(request.get_header("Authorization"), "Bearer service-token")
        self.assertEqual(request.get_header("X-owner-id"), "legacy-storage-owner")
        traces = [call.kwargs for call in self.record.call_args_list if call.kwargs['path'] == 'storage.read_url']
        self.assertEqual([item['timing_context']['cache_hit'] for item in traces], [False, True])
        self.assertTrue(all(item['timing_context']['owner_lookup_ms'] >= 0 for item in traces))
        self.assertTrue(all(item['timing_context']['file_id'] == 'file/id' for item in traces))

    def test_download_file_reads_signed_path_through_internal_storage_url(self) -> None:
        with (
            patch(
                "app.storage.settings",
                replace(storage.settings, storage_url="http://storage.internal:8090", storage_api_token="service-token"),
            ),
            patch.object(storage, "read_url", return_value="https://storage.magi00.fun/files/file-id?expires=123&signature=signed"),
            patch("app.storage.urlopen", return_value=_DownloadResponse()) as open_url,
        ):
            content, media_type = storage.download_file(file_id="file-id")

        self.assertEqual(content, b"image")
        self.assertEqual(media_type, "image/png")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://storage.internal:8090/files/file-id?expires=123&signature=signed")

    def test_delete_file_accepts_no_content(self) -> None:
        with (
            patch(
                "app.storage.settings",
                replace(storage.settings, storage_url="https://storage.example/", storage_api_token="service-token"),
            ),
            patch("app.storage.urlopen", return_value=_Response()) as open_url,
        ):
            storage.delete_file(file_id="file/id")

        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://storage.example/files/file%2Fid")
        self.assertEqual(request.get_header("Authorization"), "Bearer service-token")
        self.assertEqual(request.get_header("X-owner-id"), "legacy-storage-owner")


if __name__ == "__main__":
    unittest.main()
