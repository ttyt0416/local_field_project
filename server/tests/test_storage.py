import json
from unittest.mock import patch
from urllib.request import Request

from app import storage


class _Response:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def test_upload_file_sends_owner_and_authentication() -> None:
    with (
        patch.object(storage.settings, "storage_url", "https://storage.example"),
        patch.object(storage.settings, "storage_api_token", "service-token"),
        patch("app.storage.urlopen", return_value=_Response({"id": "file-id"})) as open_url,
    ):
        file_id = storage.upload_file(content=b"image", media_type="image/png", owner_id="user-id")

    assert file_id == "file-id"
    request = open_url.call_args.args[0]
    assert isinstance(request, Request)
    assert request.full_url == "https://storage.example/files"
    assert request.get_header("Authorization") == "Bearer service-token"
    assert request.get_header("Content-type") == "image/png"
    assert request.get_header("X-owner-id") == "user-id"
    assert request.data == b"image"


def test_read_url_uses_file_id_and_expiry() -> None:
    with (
        patch.object(storage.settings, "storage_url", "https://storage.example/"),
        patch.object(storage.settings, "storage_api_token", "service-token"),
        patch("app.storage.urlopen", return_value=_Response({"url": "https://cdn.example/file"})) as open_url,
    ):
        url = storage.read_url(file_id="file/id", owner_id="user-id", expires_in=60)

    assert url == "https://cdn.example/file"
    request = open_url.call_args.args[0]
    assert request.full_url == "https://storage.example/files/file%2Fid/url?expires_in=60"
    assert request.get_header("Authorization") == "Bearer service-token"
    assert request.get_header("X-owner-id") == "user-id"
