from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import music
from app.auth import UserResponse
from app.comfyui import _ComfyUIError


class MusicGenerationTest(unittest.TestCase):
    def test_options_report_ready_local_model(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with (
            patch.object(music, "_readiness", return_value=([], [])),
            patch.object(music, "storage_enabled", return_value=True),
        ):
            response = music.music_options(user)

        self.assertEqual(response.model, "MiniMax-Music3")
        self.assertTrue(response.service_available)
        self.assertEqual(response.max_duration_seconds, 300)

    def test_build_prompt_binds_description_lyrics_duration_and_seed(self) -> None:
        request = music.MusicGenerationRequest(
            description="dreamy synth pop with a warm female vocal",
            lyrics="[Verse]\nHello\n\n[Chorus]\nStay",
            duration_seconds=75,
            seed=123,
        )

        prompt, seed = music._build_prompt(request)

        self.assertEqual(seed, 123)
        self.assertEqual(prompt["4"]["inputs"]["caption"], request.description)
        self.assertEqual(prompt["4"]["inputs"]["lyrics"], request.lyrics)
        self.assertEqual(prompt["4"]["inputs"]["max_duration"], 75)
        self.assertEqual(prompt["4"]["inputs"]["seed"], 123)
        self.assertEqual(prompt["7"]["inputs"]["seed"], 123)
        self.assertTrue(prompt["9"]["inputs"]["filename_prefix"].startswith("LocalField_Music3_"))

    def test_workflow_has_no_dangling_dependencies_and_one_audio_output(self) -> None:
        graph = json.loads(music._WORKFLOW_PATH.read_text(encoding="utf-8"))
        dangling = []
        for node_id, node in graph.items():
            for name, value in node["inputs"].items():
                if isinstance(value, list) and len(value) == 2 and value[0] not in graph:
                    dangling.append((node_id, name, value))

        self.assertEqual(dangling, [])
        self.assertEqual(
            [node_id for node_id, node in graph.items() if node["class_type"] == "SaveAudio"],
            ["9"],
        )
        self.assertEqual(graph["7"]["inputs"]["steps"], 30)
        self.assertEqual(graph["7"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(graph["7"]["inputs"]["scheduler"], "simple")

    def test_raw_audio_output_accepts_only_supported_audio(self) -> None:
        outputs = {
            "9": {
                "audio": [
                    {"filename": "ignored.txt", "subfolder": "", "type": "output"},
                    {"filename": "song.flac", "subfolder": "audio", "type": "output"},
                ]
            }
        }

        self.assertEqual(
            music._raw_audio_output(outputs),
            {"filename": "song.flac", "subfolder": "audio", "type": "output"},
        )

    def test_sync_audio_output_uploads_strict_mime(self) -> None:
        generation = {"prompt_id": "prompt", "storage_file_id": None}
        audio = {"filename": "song.flac", "subfolder": "audio", "type": "output"}
        with (
            patch.object(music, "_request_bytes", return_value=(b"fLaC" + b"\0" * 20, "application/octet-stream")),
            patch.object(music, "storage_upload_file", return_value="file-id") as upload,
            patch.object(music, "update_music_generation_status") as update,
        ):
            music._sync_audio_output(generation, audio, uuid4())

        self.assertEqual(upload.call_args.kwargs["media_type"], "audio/flac")
        self.assertEqual(update.call_args.kwargs["status"], "completed")
        self.assertEqual(update.call_args.kwargs["size_bytes"], 24)

    def test_sync_audio_output_rejects_empty_file(self) -> None:
        generation = {"prompt_id": "prompt", "storage_file_id": None}
        audio = {"filename": "song.flac", "subfolder": "", "type": "output"}
        with (
            patch.object(music, "_request_bytes", return_value=(b"bad", "audio/flac")),
            patch.object(music, "storage_upload_file") as upload,
            patch.object(music, "update_music_generation_status"),
            self.assertRaises(_ComfyUIError),
        ):
            music._sync_audio_output(generation, audio, uuid4())
        upload.assert_not_called()

    def test_audio_magic_accepts_supported_formats(self) -> None:
        self.assertTrue(music._valid_audio_magic(b"fLaC" + b"\0" * 12, ".flac"))
        self.assertTrue(music._valid_audio_magic(b"RIFF\0\0\0\0WAVE", ".wav"))
        self.assertTrue(music._valid_audio_magic(b"ID3" + b"\0" * 12, ".mp3"))
        self.assertTrue(music._valid_audio_magic(b"OggS" + b"\0" * 12, ".ogg"))
        self.assertFalse(music._valid_audio_magic(b"not audio data", ".flac"))

    def test_readiness_requires_native_nodes_and_three_models(self) -> None:
        graph = json.loads(music._WORKFLOW_PATH.read_text(encoding="utf-8"))
        info = {node["class_type"]: {"input": {"required": {}}} for node in graph.values()}
        info["UNETLoader"]["input"]["required"]["unet_name"] = [["minimax_music3_dit_fp16.safetensors"]]
        info["CLIPLoader"]["input"]["required"]["clip_name"] = [["minimax_music3_text_encoder_pruned_int8_convrot.safetensors"]]
        info["VAELoader"]["input"]["required"]["vae_name"] = [["minimax_music3_dav.safetensors"]]

        with patch.object(music, "_request_json", return_value=info):
            self.assertEqual(music._readiness(), ([], []))


if __name__ == "__main__":
    unittest.main()
