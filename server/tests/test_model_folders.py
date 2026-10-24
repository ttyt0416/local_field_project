from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import HTTPException

from app.auth import UserResponse
from app.configs.constants import settings
from app.model_downloads import (
    CivitaiFile,
    CivitaiVersion,
    _ModelDownloadCancelled,
    _process_model_download,
    RenameModelFolderRequest,
    delete_model_folder,
    model_folder_info,
    rename_model_folder,
    retry_download,
)


class ModelFoldersTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.models = self.root / "checkpoints"
        self.models.mkdir()
        self.user = UserResponse(id=uuid.uuid4(), username="folder-tester")
        settings_patch = patch("app.model_downloads.settings", replace(settings, comfyui_models_path=str(self.root)))
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        active_patch = patch("app.model_downloads.has_active_model_downloads_under", return_value=False)
        self.active_downloads = active_patch.start()
        self.addCleanup(active_patch.stop)

    def tree(self, name: str = "styles/원본") -> Path:
        folder = self.models / name
        (folder / "nested/empty").mkdir(parents=True)
        (folder / "model.safetensors").write_bytes(b"model")
        (folder / "nested/preview.png").write_bytes(b"image")
        (folder / ".metadata.json").write_bytes(b"config")
        return folder

    def test_info_counts_nested_and_non_model_files_and_is_stable(self) -> None:
        self.tree()
        info = model_folder_info("checkpoint", "styles/원본", self.user)
        again = model_folder_info("checkpoint", "styles/원본", self.user)
        self.assertEqual((info.file_count, info.directory_count, info.size_bytes), (3, 2, 16))
        self.assertEqual(info.revision, again.revision)
        self.assertFalse(info.has_active_downloads)

    def test_rename_keeps_all_descendants_and_sibling_files(self) -> None:
        folder = self.tree()
        sibling = self.models / "styles/sibling.safetensors"
        sibling.write_bytes(b"sibling")
        result = rename_model_folder("checkpoint", RenameModelFolderRequest(subfolder="styles/원본", name="새 이름 #1"), self.user)
        destination = self.models / "styles/새 이름 #1"
        self.assertEqual(result.subfolder, "styles/새 이름 #1")
        self.assertFalse(folder.exists())
        self.assertEqual((destination / "model.safetensors").read_bytes(), b"model")
        self.assertEqual((destination / "nested/preview.png").read_bytes(), b"image")
        self.assertTrue((destination / "nested/empty").is_dir())
        self.assertEqual(sibling.read_bytes(), b"sibling")

    def test_recursive_delete_includes_hidden_sidecars_and_preserves_siblings(self) -> None:
        folder = self.tree("Anima")
        sibling = self.models / "Anima-extra"
        sibling.mkdir()
        (sibling / "keep.bin").write_bytes(b"keep")
        info = model_folder_info("checkpoint", "Anima", self.user)
        delete_model_folder("checkpoint", "Anima", info.revision, self.user)
        self.assertFalse(folder.exists())
        self.assertEqual((sibling / "keep.bin").read_bytes(), b"keep")
        self.assertTrue(self.models.is_dir())

    def test_empty_folder_can_be_renamed_and_deleted(self) -> None:
        (self.models / "empty").mkdir()
        rename_model_folder("checkpoint", RenameModelFolderRequest(subfolder="empty", name="renamed"), self.user)
        info = model_folder_info("checkpoint", "renamed", self.user)
        self.assertEqual((info.file_count, info.directory_count, info.size_bytes), (0, 0, 0))
        delete_model_folder("checkpoint", "renamed", info.revision, self.user)
        self.assertFalse((self.models / "renamed").exists())

    def test_changed_contents_require_a_new_delete_confirmation(self) -> None:
        folder = self.tree()
        old = model_folder_info("checkpoint", "styles/원본", self.user)
        (folder / "nested/new.txt").write_bytes(b"new")
        with self.assertRaises(HTTPException) as raised:
            delete_model_folder("checkpoint", "styles/원본", old.revision, self.user)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertTrue((folder / "model.safetensors").exists())
        updated = model_folder_info("checkpoint", "styles/원본", self.user)
        delete_model_folder("checkpoint", "styles/원본", updated.revision, self.user)
        self.assertFalse(folder.exists())

    def test_active_download_blocks_rename_and_delete(self) -> None:
        folder = self.tree()
        info = model_folder_info("checkpoint", "styles/원본", self.user)
        self.active_downloads.return_value = True
        self.assertTrue(model_folder_info("checkpoint", "styles/원본", self.user).has_active_downloads)
        for operation in (
            lambda: rename_model_folder("checkpoint", RenameModelFolderRequest(subfolder="styles/원본", name="new"), self.user),
            lambda: delete_model_folder("checkpoint", "styles/원본", info.revision, self.user),
        ):
            with self.assertRaises(HTTPException) as raised:
                operation()
            self.assertEqual(raised.exception.status_code, 409)
        self.assertTrue(folder.exists())
        self.active_downloads.assert_called_with(str(folder))

    def test_rename_does_not_replace_an_existing_empty_folder(self) -> None:
        self.tree("source")
        (self.models / "existing").mkdir()
        with self.assertRaises(HTTPException) as raised:
            rename_model_folder("checkpoint", RenameModelFolderRequest(subfolder="source", name="existing"), self.user)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertTrue((self.models / "source/model.safetensors").exists())
        self.assertTrue((self.models / "existing").is_dir())

    def test_basic_roots_and_unsafe_source_paths_cannot_be_modified(self) -> None:
        for path in ("", " ", ".", "..", "../checkpoints", "/checkpoints", "a/../b", ".cache", "a\\b"):
            with self.subTest(path=path):
                with self.assertRaises(HTTPException):
                    model_folder_info("checkpoint", path, self.user)
                with self.assertRaises(HTTPException):
                    delete_model_folder("checkpoint", path, "0" * 64, self.user)
        self.assertTrue(self.models.is_dir())

    def test_rename_rejects_unsafe_names_and_retains_source(self) -> None:
        self.tree("source")
        for name in (" ", ".", "..", ".hidden", "../outside", "nested/name", "back\\slash", "C:drive", "bad\nname"):
            with self.subTest(name=name), self.assertRaises(HTTPException):
                rename_model_folder("checkpoint", RenameModelFolderRequest(subfolder="source", name=name), self.user)
        self.assertTrue((self.models / "source/model.safetensors").is_file())

    def test_symlink_source_and_symlink_model_root_are_rejected(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        keep = outside / "keep.bin"
        keep.write_bytes(b"outside")
        (self.models / "link").symlink_to(outside, target_is_directory=True)
        (self.root / "loras").symlink_to(outside, target_is_directory=True)
        for type_, path in (("checkpoint", "link"), ("checkpoint", "link/nested"), ("lora", "nested")):
            with self.subTest(type_=type_, path=path), self.assertRaises(HTTPException):
                delete_model_folder(type_, path, "0" * 64, self.user)
        self.assertEqual(keep.read_bytes(), b"outside")

    def test_recursive_delete_unlinks_descendant_symlink_without_following_it(self) -> None:
        folder = self.tree("source")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep.bin").write_bytes(b"outside")
        (folder / "outside-link").symlink_to(outside, target_is_directory=True)
        info = model_folder_info("checkpoint", "source", self.user)
        self.assertEqual(info.file_count, 4)
        delete_model_folder("checkpoint", "source", info.revision, self.user)
        self.assertEqual((outside / "keep.bin").read_bytes(), b"outside")

    def test_missing_folder_has_no_filesystem_side_effects(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            rename_model_folder("checkpoint", RenameModelFolderRequest(subfolder="missing", name="new"), self.user)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertFalse((self.models / "new").exists())

    def test_rename_cannot_create_an_unaddressable_overlong_folder_path(self) -> None:
        parent = f"{'a' * 100}/{'b' * 100}"
        source = self.models / parent / "source"
        source.mkdir(parents=True)
        with self.assertRaises(HTTPException) as raised:
            rename_model_folder("checkpoint", RenameModelFolderRequest(subfolder=f"{parent}/source", name="c" * 120), self.user)
        self.assertEqual(raised.exception.status_code, 422)
        self.assertTrue(source.is_dir())

    def test_retry_does_not_recreate_a_deleted_download_folder(self) -> None:
        previous = {"model_type": "checkpoint", "target_path": str(self.models / "deleted/model.safetensors")}
        with patch("app.model_downloads.get_model_download", return_value=previous), patch("app.model_downloads.retry_model_download") as retry:
            with self.assertRaises(HTTPException) as raised:
                retry_download(uuid.uuid4(), self.user)
            self.assertEqual(raised.exception.status_code, 409)
            retry.assert_not_called()
        self.assertFalse((self.models / "deleted").exists())

    def test_cancelled_worker_cannot_recreate_a_deleted_download_folder(self) -> None:
        target = self.models / "deleted/model.safetensors"
        version = CivitaiVersion(1, None, "Model", "Checkpoint", "v1", None, (CivitaiFile(target.name, "Model", "https://civitai.com/file", 1, None, True),))
        with (
            patch("app.model_downloads.settings", replace(settings, comfyui_models_path=str(self.root), civitai_token="test-only")),
            patch("app.model_downloads._fetch_version", return_value=version),
            patch("app.model_downloads.is_model_download_active", return_value=False),
            patch("app.model_downloads._open_download") as open_download,
        ):
            with self.assertRaises(_ModelDownloadCancelled):
                _process_model_download({"id": uuid.uuid4(), "version_id": 1, "model_type": "checkpoint", "file_index": 0, "target_path": str(target)})
            open_download.assert_not_called()
        self.assertFalse(target.parent.exists())


if __name__ == "__main__":
    unittest.main()
