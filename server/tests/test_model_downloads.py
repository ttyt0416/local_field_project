from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

from fastapi import HTTPException

from app.auth import UserResponse
from app.configs.constants import settings
from app.model_downloads import (
    CivitaiError,
    CivitaiFile,
    CivitaiVersion,
    _ModelDownloadCancelled,
    _file_matches,
    _installed_model_path,
    _parse_version,
    _process_model_download,
    _safe_filename,
    _select_file_index,
    ModelType,
    cancel_download,
    delete_installed_model,
)


class ModelDownloadsTest(unittest.TestCase):
    def test_parses_civitai_version_file_contract(self) -> None:
        version = _parse_version(
            {
                "name": "Example v1",
                "baseModel": "SDXL 1.0",
                "model": {"id": 123, "name": "Example", "type": "Checkpoint"},
                "files": [
                    {
                        "name": "example.safetensors",
                        "type": "Model",
                        "downloadUrl": "https://civitai.com/api/download/models/123",
                        "sizeKB": 2048,
                        "primary": True,
                        "hashes": {"SHA256": "ABC123"},
                    }
                ],
            },
            456,
        )
        self.assertEqual(version.version_id, 456)
        self.assertEqual(version.model_type, "Checkpoint")
        self.assertEqual(version.files[0].size_bytes, 2 * 1024 * 1024)
        self.assertEqual(version.files[0].sha256, "ABC123")
        self.assertEqual(_select_file_index(version, "checkpoint", None), 0)

    def test_model_type_mapping_covers_requested_types(self) -> None:
        cases = {
            "checkpoint": ("Checkpoint", "Model"),
            "lora": ("LoCon", "Model"),
            "text_encoder": ("TextEncoder", "Model"),
            "vae": ("VAE", "Model"),
            "embedding": ("TextualInversion", "Model"),
        }
        for requested_type, (version_type, file_type) in cases.items():
            version = _parse_version(
                {
                    "model": {"type": version_type},
                    "files": [{"name": "model.safetensors", "type": file_type, "downloadUrl": "https://civitai.com/file"}],
                },
                1,
            )
            self.assertTrue(_file_matches(version, version.files[0], cast(ModelType, requested_type)))

        version = _parse_version(
            {
                "model": {"type": "Other"},
                "files": [{"name": "AnimaTextEncoder.safetensors", "type": "Model", "downloadUrl": "https://civitai.com/file"}],
            },
            1,
        )
        self.assertTrue(_file_matches(version, version.files[0], "text_encoder"))

    def test_safe_filename_removes_path_and_rejects_unsupported_files(self) -> None:
        self.assertEqual(_safe_filename("nested\\folder\\model.safetensors"), "model.safetensors")
        with self.assertRaises(CivitaiError):
            _safe_filename("model.zip")
        with self.assertRaises(CivitaiError):
            _safe_filename("../model.safetensors\n")

    def test_installed_model_delete_stays_inside_model_directory(self) -> None:
        user = UserResponse(id=uuid.uuid4(), username="tester")
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            model_directory = root / "checkpoints"
            model_directory.mkdir()
            model = model_directory / "model.safetensors"
            model.write_bytes(b"model")
            outside = root / "outside.safetensors"
            outside.write_bytes(b"outside")
            link = model_directory / "link.safetensors"
            link.symlink_to(outside)

            with patch(
                "app.model_downloads.settings",
                replace(settings, comfyui_models_path=temporary_directory),
            ):
                delete_installed_model("checkpoint", "model.safetensors", user)
                self.assertFalse(model.exists())
                self.assertEqual(
                    _installed_model_path("checkpoint", "nested/model.safetensors"),
                    model_directory / "nested/model.safetensors",
                )
                with self.assertRaises(HTTPException) as traversal_error:
                    _installed_model_path("checkpoint", "../outside.safetensors")
                with self.assertRaises(HTTPException) as symlink_error:
                    _installed_model_path("checkpoint", "link.safetensors")

            linked_root = root / "linked-root"
            linked_root.mkdir()
            linked_model_directory = root / "linked-checkpoints"
            linked_model_directory.mkdir()
            (linked_root / "checkpoints").symlink_to(linked_model_directory, target_is_directory=True)
            with patch(
                "app.model_downloads.settings",
                replace(settings, comfyui_models_path=str(linked_root)),
            ):
                with self.assertRaises(HTTPException) as linked_directory_error:
                    _installed_model_path("checkpoint", "model.safetensors")

            self.assertEqual(traversal_error.exception.status_code, 400)
            self.assertEqual(symlink_error.exception.status_code, 400)
            self.assertEqual(linked_directory_error.exception.status_code, 400)
            self.assertTrue(outside.exists())

    def test_cancelled_download_deletes_partial_file(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "checkpoints" / "model.safetensors"
            target.parent.mkdir()
            partial = target.with_name(f".{target.name}.part")
            partial.write_bytes(b"partial")
            version = CivitaiVersion(
                version_id=1,
                model_id=None,
                model_name="Example",
                model_type="Checkpoint",
                version_name="v1",
                base_model=None,
                files=(
                    CivitaiFile(
                        name="model.safetensors",
                        file_type="Model",
                        download_url="https://civitai.com/file",
                        size_bytes=7,
                        sha256=None,
                        primary=True,
                    ),
                ),
            )
            job = {"id": uuid.uuid4(), "version_id": 1, "model_type": "checkpoint", "file_index": 0, "target_path": str(target)}

            class DownloadResponse:
                status = 200
                headers: dict[str, str] = {}

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return None

            with (
                patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary_directory, civitai_token="token")),
                patch("app.model_downloads._fetch_version", return_value=version),
                patch("app.model_downloads._open_download", return_value=DownloadResponse()),
                patch("app.model_downloads.is_model_download_active", return_value=True),
                patch("app.model_downloads.update_model_download_progress", return_value=False),
            ):
                with self.assertRaises(_ModelDownloadCancelled):
                    _process_model_download(job)

            self.assertFalse(partial.exists())
            self.assertFalse(target.exists())

    def test_cancel_endpoint_deletes_partial_file_before_returning(self) -> None:
        user = UserResponse(id=uuid.uuid4(), username="tester")
        with TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "checkpoints" / "model.safetensors"
            partial = target.with_name(f".{target.name}.part")
            partial.parent.mkdir()
            partial.write_bytes(b"partial")
            row = {
                "id": uuid.uuid4(),
                "user_id": user.id,
                "version_id": 1,
                "model_type": "checkpoint",
                "filename": target.name,
                "target_path": str(target),
                "status": "cancelled",
                "downloaded_bytes": 7,
                "total_bytes": 7,
                "error_message": "다운로드가 중단되었습니다.",
                "created_at": datetime.now(timezone.utc),
                "completed_at": None,
            }
            with patch("app.model_downloads.cancel_model_download", return_value=row):
                response = cancel_download(row["id"], user)

            self.assertEqual(response.status, "cancelled")
            self.assertFalse(partial.exists())


if __name__ == "__main__":
    unittest.main()
