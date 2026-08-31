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
    _model_target_directory,
    _fetch_model_versions,
    _lookup_response,
    _parse_civitai_source,
    _parse_version,
    _process_model_download,
    _resolve_civitai_source,
    _safe_subfolder,
    _safe_filename,
    _select_file_index,
    _detected_model_type,
    ModelType,
    cancel_download,
    create_model_folder,
    delete_installed_model,
    download_civitai_model,
    ModelDownloadRequest,
    ModelFolderRequest,
    MoveInstalledModelRequest,
    list_model_folders,
    move_installed_model,
)


class ModelDownloadsTest(unittest.TestCase):
    def test_model_page_source_and_version_paths_are_distinct(self) -> None:
        self.assertEqual(
            _parse_civitai_source("https://civitai.red/models/1145743/example"),
            (1145743, None),
        )
        self.assertEqual(
            _parse_civitai_source("https://civitai.com/models/1145743/example?modelVersionId=3271822"),
            (1145743, 3271822),
        )
        self.assertEqual(
            _parse_civitai_source("https://civitai.com/api/download/models/3271822"),
            (None, 3271822),
        )
        with self.assertRaises(CivitaiError):
            _parse_civitai_source("https://example.com/models/1145743/example")

    def test_model_versions_use_latest_compatible_published_version(self) -> None:
        payload = {
            "id": 1145743,
            "name": "Example",
            "type": "LORA",
            "modelVersions": [
                {
                    "id": 10,
                    "name": "Older",
                    "publishedAt": "2026-01-01T00:00:00Z",
                    "files": [{"name": "older.safetensors", "type": "Model", "downloadUrl": "https://civitai.com/file/10"}],
                },
                {
                    "id": 30,
                    "name": "Unsupported newest",
                    "publishedAt": "2026-03-01T00:00:00Z",
                    "files": [{"name": "archive.zip", "type": "Model", "downloadUrl": "https://civitai.com/file/30"}],
                },
                {
                    "id": 20,
                    "name": "Latest compatible",
                    "publishedAt": "2026-02-01T00:00:00Z",
                    "files": [{"name": "latest.safetensors", "type": "Model", "downloadUrl": "https://civitai.com/file/20"}],
                },
            ],
        }
        with patch("app.model_downloads._fetch_civitai_payload", return_value=payload):
            versions = _fetch_model_versions(1145743, "lora")

        self.assertEqual([version.version_id for version in versions], [20, 10])

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
            "diffusion_model": ("Checkpoint", "Model"),
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

    def test_lookup_auto_changes_checkpoint_diffusion_and_lora_destinations(self) -> None:
        cases = (
            ("Checkpoint", "Anima", "diffusion_model", "Anima"),
            ("Checkpoint", "MiniMax H3", "diffusion_model", "MiniMaxH3"),
            ("Checkpoint", "Illustrious", "checkpoint", "Illustrious"),
            ("LORA", "Illustrious", "lora", "Illustrious"),
        )
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for folder in ("diffusion_models/Anima", "diffusion_models/MiniMaxH3", "checkpoints/Illustrious", "loras/Illustrious"):
                (root / folder).mkdir(parents=True)
            with patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary_directory)):
                for civitai_type, base_model, expected_type, expected_folder in cases:
                    version = CivitaiVersion(
                        version_id=1,
                        model_id=None,
                        model_name="Example",
                        model_type=civitai_type,
                        version_name="v1",
                        base_model=base_model,
                        files=(CivitaiFile("model.safetensors", "Model", "https://civitai.com/file", 1, None, True),),
                    )
                    response = _lookup_response(version, _detected_model_type(version) or "checkpoint", 0, (version,))
                    self.assertEqual(response.target_model_type, expected_type)
                    self.assertEqual(response.suggested_subfolder, expected_folder)

                lora = CivitaiVersion(1, None, "Example", "LORA", "v1", "Illustrious", (CivitaiFile("model.safetensors", "Model", "https://civitai.com/file", 1, None, True),))
                with patch("app.model_downloads._fetch_version", return_value=lora):
                    _, target_type, _, _ = _resolve_civitai_source("1", "checkpoint", None)
                self.assertEqual(target_type, "lora")

                (root / "loras/styles/Anima").mkdir(parents=True)
                nested = CivitaiVersion(1, None, "Example", "LORA", "v1", "Anima", (CivitaiFile("model.safetensors", "Model", "https://civitai.com/file", 1, None, True),))
                nested_response = _lookup_response(nested, "lora", 0, (nested,))
                self.assertEqual(nested_response.suggested_subfolder, "styles/Anima")

    def test_model_storage_categories_are_distinct(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for folder in ("checkpoints", "diffusion_models", "loras", "embeddings"):
                (root / folder).mkdir()
            with patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary_directory)):
                self.assertEqual(_model_target_directory("checkpoint", "Illustrious"), root / "checkpoints/Illustrious")
                self.assertEqual(_model_target_directory("diffusion_model", "Anima"), root / "diffusion_models/Anima")
                self.assertEqual(_model_target_directory("lora", "Illustrious"), root / "loras/Illustrious")
                self.assertEqual(_model_target_directory("embedding", "Illustrious"), root / "embeddings/Illustrious")

    def test_safe_filename_removes_path_and_rejects_unsupported_files(self) -> None:
        self.assertEqual(_safe_filename("nested\\folder\\model.safetensors"), "model.safetensors")
        with self.assertRaises(CivitaiError):
            _safe_filename("model.zip")
        with self.assertRaises(CivitaiError):
            _safe_filename("../model.safetensors\n")

    def test_safe_subfolder_allows_relative_nested_path_only(self) -> None:
        self.assertEqual(_safe_subfolder(" characters/anime "), "characters/anime")
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "checkpoints").mkdir()
            with patch(
                "app.model_downloads.settings",
                replace(settings, comfyui_models_path=temporary_directory),
            ):
                self.assertEqual(
                    _model_target_directory("checkpoint", "characters/anime"),
                    root / "checkpoints/characters/anime",
                )

                outside = root / "outside"
                outside.mkdir()
                (root / "checkpoints/linked").symlink_to(outside, target_is_directory=True)
                with self.assertRaises(CivitaiError):
                    _model_target_directory("checkpoint", "linked/nested")

        for invalid in ("../outside", "/outside", "characters\\anime", "characters//anime", "characters/./anime", "C:/outside", "characters\x00/anime"):
            with self.assertRaises(CivitaiError):
                _safe_subfolder(invalid)

    def test_existing_folders_can_be_listed_and_new_folder_created(self) -> None:
        user = UserResponse(id=uuid.uuid4(), username="tester")
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "loras"
            (root / "character/anime").mkdir(parents=True)
            (root / ".cache/internal").mkdir(parents=True)
            with patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary_directory)):
                folders = list_model_folders("lora", user)
                created = create_model_folder(ModelFolderRequest(model_type="lora", parent="character", name="realistic"), user)
                with self.assertRaises(HTTPException) as duplicate:
                    create_model_folder(ModelFolderRequest(model_type="lora", parent="character", name="realistic"), user)
                with self.assertRaises(HTTPException) as invalid_name:
                    create_model_folder(ModelFolderRequest(model_type="lora", name="style/anime"), user)
                with self.assertRaises(HTTPException) as hidden_parent:
                    create_model_folder(ModelFolderRequest(model_type="lora", parent=".cache", name="new"), user)

            self.assertEqual([folder.subfolder for folder in folders], ["", "character", "character/anime"])
            self.assertEqual(created.subfolder, "character/realistic")
            self.assertTrue((root / "character/realistic").is_dir())
            self.assertEqual(duplicate.exception.status_code, 409)
            self.assertEqual(invalid_name.exception.status_code, 400)
            self.assertEqual(hidden_parent.exception.status_code, 400)

    def test_download_request_uses_subfolder_in_target_path(self) -> None:
        user = UserResponse(id=uuid.uuid4(), username="tester")
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
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.mkdir(exist_ok=True)
            target = root / "checkpoints/characters/anime/model.safetensors"
            target.parent.mkdir(parents=True)
            row = {
                "id": uuid.uuid4(),
                "version_id": 1,
                "model_type": "checkpoint",
                "target_path": str(target),
                "filename": "model.safetensors",
                "status": "queued",
                "downloaded_bytes": 0,
                "total_bytes": 7,
                "error_message": None,
                "created_at": datetime.now(timezone.utc),
                "completed_at": None,
            }
            with (
                patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary_directory, civitai_token="token")),
                patch("app.model_downloads._fetch_version", return_value=version),
                patch("app.model_downloads.create_model_download", return_value=row) as create_job,
            ):
                response = download_civitai_model(
                    ModelDownloadRequest(source="1", model_type="checkpoint", file_index=0, subfolder="characters/anime"),
                    user,
                )

            self.assertEqual(create_job.call_args.kwargs["target_path"], str(target))
            self.assertEqual(response.subfolder, "characters/anime")
            self.assertEqual(response.filename, "model.safetensors")

    def test_installed_model_can_move_to_existing_nested_folder(self) -> None:
        user = UserResponse(id=uuid.uuid4(), username="tester")
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "checkpoints" / "model.safetensors"
            destination = root / "checkpoints" / "characters" / "anime" / source.name
            source.parent.mkdir()
            destination.parent.mkdir(parents=True)
            source.write_bytes(b"model")
            with patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary_directory)):
                moved = move_installed_model(
                    "checkpoint",
                    MoveInstalledModelRequest(filename="model.safetensors", subfolder="characters/anime"),
                    user,
                )
                with self.assertRaises(HTTPException) as collision:
                    (root / "checkpoints" / "other.safetensors").write_bytes(b"other")
                    (destination.parent / "other.safetensors").write_bytes(b"existing")
                    move_installed_model(
                        "checkpoint",
                        MoveInstalledModelRequest(filename="other.safetensors", subfolder="characters/anime"),
                        user,
                    )

            self.assertEqual(moved.filename, "characters/anime/model.safetensors")
            self.assertEqual(destination.read_bytes(), b"model")
            self.assertFalse(source.exists())
            self.assertEqual(collision.exception.status_code, 409)

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
