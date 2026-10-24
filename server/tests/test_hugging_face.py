from __future__ import annotations

import hashlib
import io
import json
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from fastapi import HTTPException

from app import hugging_face as hf
from app import model_downloads as models
from app.auth import UserResponse
from app.configs.constants import settings


COMMIT = "a" * 40
CONTENTS = b"synthetic model bytes"
SHA = hashlib.sha256(CONTENTS).hexdigest()
REPOSITORY = hf.HuggingFaceRepository("owner/repo", COMMIT, (hf.HuggingFaceFile("nested/model.safetensors", len(CONTENTS), SHA),))


class Response(io.BytesIO):
    def __init__(self, data: bytes, status: int = 200, headers: dict[str, str] | None = None):
        super().__init__(data)
        self.status = status
        self.headers = headers if headers is not None else {"Content-Length": str(len(data))}


class HuggingFaceTest(unittest.TestCase):
    def test_parses_repository_file_folder_and_encoded_revision_links(self) -> None:
        for source, revision, path, file in (
            ("owner/repo", "main", "", False),
            ("https://huggingface.co/owner/repo", "main", "", False),
            ("https://huggingface.co/owner/repo/blob/main/nested/model.safetensors?download=true", "main", "nested/model.safetensors", True),
            ("https://huggingface.co/owner/repo/resolve/refs%2Fpr%2F2/model.safetensors", "refs/pr/2", "model.safetensors", True),
            ("https://huggingface.co/owner/repo/tree/main/nested", "main", "nested", False),
        ):
            with self.subTest(source=source):
                parsed = hf.parse_source(source)
                self.assertEqual((parsed.repo_id, parsed.revision, parsed.path, parsed.is_file), ("owner/repo", revision, path, file))
        self.assertEqual(hf.parse_source("owner/repo", "release/v1").revision, "release/v1")
        self.assertEqual(hf.parse_source("https://huggingface.co/owner/tree").repo_id, "owner/tree")

    def test_rejects_foreign_hosts_credentials_traversal_and_non_model_repositories(self) -> None:
        for source in ("https://example.com/owner/repo", "http://huggingface.co/owner/repo", "https://secret@huggingface.co/owner/repo", "https://huggingface.co:443/owner/repo", "https://huggingface.co/datasets/owner/repo", "../repo", "owner/repo/extra", "https://huggingface.co/owner/repo/blob/main/%2e%2e/model.safetensors"):
            with self.subTest(source=source), self.assertRaises(hf.HuggingFaceError):
                hf.parse_source(source)

    def test_metadata_filters_model_files_and_preserves_paths_sizes_and_lfs_hash(self) -> None:
        payload = {"sha": COMMIT, "siblings": [
            {"rfilename": "nested/model.safetensors", "size": len(CONTENTS), "lfs": {"sha256": SHA, "size": len(CONTENTS)}},
            {"rfilename": "model.gguf", "size": 9},
            {"rfilename": "README.md", "size": 50},
            {"rfilename": "../bad.safetensors", "size": 5},
        ]}
        opener = Mock()
        opener.open.return_value = Response(json.dumps(payload).encode())
        repository = hf.fetch_repository("owner/repo", "release/v1", "test-token", opener, models._MODEL_EXTENSIONS)
        self.assertEqual(repository.revision, COMMIT)
        self.assertEqual([file.path for file in repository.files], ["model.gguf", "nested/model.safetensors"])
        self.assertEqual(repository.files[1].sha256, SHA)
        request = opener.open.call_args.args[0]
        self.assertIn("/revision/release%2Fv1?blobs=true", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_metadata_rejects_missing_and_mismatched_commits(self) -> None:
        for sha in (None, "not-a-commit", "b" * 40):
            opener = Mock()
            opener.open.return_value = Response(json.dumps({"sha": sha, "siblings": []}).encode())
            with self.subTest(sha=sha), self.assertRaises(hf.HuggingFaceError):
                hf.fetch_repository("owner/repo", COMMIT, "", opener, models._MODEL_EXTENSIONS)

    def test_redirect_strips_token_for_official_cdn_and_keeps_range(self) -> None:
        headers = Message()
        headers["Location"] = "https://cas-bridge.xethub.hf.co/fixture?signature=test"
        opener = Mock()
        opener.open.side_effect = [HTTPError("https://huggingface.co/owner/repo/resolve/main/model", 302, "redirect", headers, None), Response(b"body")]
        hf.open_download(hf.file_url("owner/repo", COMMIT, "model.safetensors"), "test-token", 3, opener)
        first, second = [call.args[0] for call in opener.open.call_args_list]
        self.assertEqual(first.get_header("Authorization"), "Bearer test-token")
        self.assertIsNone(second.get_header("Authorization"))
        self.assertEqual(second.get_header("Range"), "bytes=3-")

    def test_redirect_to_foreign_host_is_rejected_before_contacting_it(self) -> None:
        for url in ("http://huggingface.co/file", "https://127.0.0.1/file", "https://hf.co.evil.example/file", "https://user@cdn-lfs.hf.co/file", "https://cdn-lfs.hf.co:9000/file"):
            headers = Message()
            headers["Location"] = url
            opener = Mock()
            opener.open.side_effect = HTTPError("https://huggingface.co/file", 302, "redirect", headers, None)
            with self.subTest(url=url), self.assertRaises(hf.HuggingFaceError):
                hf.open_download("https://huggingface.co/file", "secret", 0, opener)
            self.assertEqual(opener.open.call_count, 1)

    def test_auth_error_does_not_include_token_or_signed_url(self) -> None:
        opener = Mock()
        opener.open.side_effect = HTTPError("https://huggingface.co/file?token=secret", 403, "secret", Message(), None)
        with self.assertRaises(hf.HuggingFaceError) as raised:
            hf.open_download("https://huggingface.co/file", "secret", 0, opener)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertNotIn("secret", str(raised.exception))

    def test_lookup_file_and_folder_links_only_return_requested_models(self) -> None:
        user = UserResponse(id=uuid.uuid4(), username="tester")
        with patch("app.model_downloads.hf.fetch_repository", return_value=REPOSITORY):
            for source in ("https://huggingface.co/owner/repo/tree/main/nested", "https://huggingface.co/owner/repo/blob/main/nested/model.safetensors"):
                response = models.lookup_hugging_face_model(source, "", user)
                self.assertEqual(response.selected_file_path, "nested/model.safetensors")
                self.assertEqual(response.revision, COMMIT)
            with self.assertRaises(HTTPException) as missing:
                models.lookup_hugging_face_model("https://huggingface.co/owner/repo/blob/main/missing.safetensors", "", user)
            self.assertEqual(missing.exception.status_code, 404)

    def test_download_queues_pinned_metadata_without_secret_or_signed_url(self) -> None:
        user = UserResponse(id=uuid.uuid4(), username="tester")
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "loras/nested/model.safetensors"
            target.parent.mkdir(parents=True)
            row = {"id": uuid.uuid4(), "version_id": 0, "provider": "hugging_face", "source_repo": "owner/repo", "source_revision": COMMIT, "source_filename": "nested/model.safetensors", "model_type": "lora", "filename": target.name, "target_path": str(target), "status": "queued", "downloaded_bytes": 0, "total_bytes": None, "error_message": None, "created_at": datetime.now(timezone.utc), "completed_at": None}
            with patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary, hugging_face_token="secret")), patch("app.model_downloads.hf.fetch_repository", return_value=REPOSITORY), patch("app.model_downloads.create_model_download", return_value=row) as create:
                payload = models.HuggingFaceDownloadRequest(repo_id="owner/repo", revision=COMMIT, filename="nested/model.safetensors", model_type="lora", subfolder="nested")
                response = models.download_hugging_face_model(payload, user)
                self.assertEqual(create.call_args.kwargs["source_revision"], COMMIT)
                self.assertEqual(create.call_args.kwargs["target_path"], str(target))
                self.assertNotIn("secret", json.dumps(create.call_args.kwargs, default=str))
                self.assertNotIn("https://", response.model_dump_json())
                self.assertIsNone(response.version_id)
                target.write_bytes(b"existing")
                with self.assertRaises(HTTPException) as duplicate:
                    models.download_hugging_face_model(payload, user)
                self.assertEqual(duplicate.exception.status_code, 409)
                self.assertEqual(create.call_count, 1)


class HuggingFaceWorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name) / "checkpoints/model.safetensors"
        self.target.parent.mkdir()
        self.job = {"id": uuid.uuid4(), "provider": "hugging_face", "version_id": 0, "model_type": "checkpoint", "file_index": 0, "target_path": str(self.target), "source_repo": "owner/repo", "source_revision": COMMIT, "source_filename": "nested/model.safetensors"}
        for name, value in (("settings", replace(settings, comfyui_models_path=temporary.name, civitai_token="", hugging_face_token="")), ("hf.fetch_repository", REPOSITORY), ("is_model_download_active", True), ("update_model_download_progress", True), ("complete_model_download", True)):
            patcher = patch(f"app.model_downloads.{name}", return_value=value) if name != "settings" else patch("app.model_downloads.settings", value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_public_download_does_not_require_civitai_or_hugging_face_token(self) -> None:
        with patch("app.model_downloads.hf.open_download", return_value=Response(CONTENTS)), patch("app.model_downloads._fetch_version") as civitai:
            models._process_model_download(self.job)
        self.assertEqual(self.target.read_bytes(), CONTENTS)
        civitai.assert_not_called()
        self.assertFalse(models._job_partial_path(self.job).exists())

    def test_resume_appends_only_matching_content_range(self) -> None:
        partial = models._job_partial_path(self.job)
        partial.write_bytes(CONTENTS[:3])
        response = Response(CONTENTS[3:], 206, {"Content-Length": str(len(CONTENTS) - 3), "Content-Range": f"bytes 3-{len(CONTENTS)-1}/{len(CONTENTS)}"})
        with patch("app.model_downloads.hf.open_download", return_value=response) as opener:
            models._process_model_download(self.job)
        self.assertEqual(opener.call_args.args[2], 3)
        self.assertEqual(self.target.read_bytes(), CONTENTS)

    def test_ignored_range_restarts_instead_of_appending(self) -> None:
        models._job_partial_path(self.job).write_bytes(b"old")
        with patch("app.model_downloads.hf.open_download", return_value=Response(CONTENTS)):
            models._process_model_download(self.job)
        self.assertEqual(self.target.read_bytes(), CONTENTS)

    def test_complete_partial_is_verified_without_requesting_an_invalid_range(self) -> None:
        models._job_partial_path(self.job).write_bytes(CONTENTS)
        with patch("app.model_downloads.hf.open_download") as opener:
            models._process_model_download(self.job)
        opener.assert_not_called()
        self.assertEqual(self.target.read_bytes(), CONTENTS)

    def test_checksum_mismatch_and_truncation_never_publish_a_model(self) -> None:
        for data, headers in ((b"x" * len(CONTENTS), None), (b"short", {"Content-Length": str(len(CONTENTS))})):
            with self.subTest(data=data), patch("app.model_downloads.hf.open_download", return_value=Response(data, headers=headers)):
                with self.assertRaises(models.CivitaiError):
                    models._process_model_download(self.job)
                self.assertFalse(self.target.exists())

    def test_bad_range_never_modifies_existing_partial(self) -> None:
        partial = models._job_partial_path(self.job)
        partial.write_bytes(b"old")
        with patch("app.model_downloads.hf.open_download", return_value=Response(CONTENTS, 206, {"Content-Range": "bytes 0-20/21"})):
            with self.assertRaises(models.CivitaiError):
                models._process_model_download(self.job)
        self.assertEqual(partial.read_bytes(), b"old")
        self.assertFalse(self.target.exists())

    def test_distinct_jobs_and_cancel_use_separate_partial_files(self) -> None:
        first = models._job_partial_path(self.job)
        second = models._job_partial_path({**self.job, "id": uuid.uuid4()})
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        row = {**self.job, "filename": self.target.name, "status": "cancelled", "downloaded_bytes": 0, "total_bytes": None, "error_message": None, "created_at": datetime.now(timezone.utc), "completed_at": None}
        user = UserResponse(id=uuid.uuid4(), username="tester")
        with patch("app.model_downloads.cancel_model_download", return_value=row):
            models.cancel_download(self.job["id"], user)
        self.assertFalse(first.exists())
        self.assertEqual(second.read_bytes(), b"second")


if __name__ == "__main__":
    unittest.main()
