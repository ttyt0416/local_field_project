from __future__ import annotations

import unittest
from typing import cast

from app.model_downloads import (
    CivitaiError,
    _file_matches,
    _parse_version,
    _safe_filename,
    _select_file_index,
    ModelType,
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


if __name__ == "__main__":
    unittest.main()
