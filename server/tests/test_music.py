from __future__ import annotations

import json
import re
import unittest
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError
from starlette.requests import Request

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
        self.assertEqual(response.detail, "")
        self.assertEqual(response.max_duration_seconds, 300)

    def test_description_enhancement_uses_selected_languages_and_strict_schema(self) -> None:
        payload = music.MusicPromptEnhancementRequest(
            target="description",
            description="따뜻한 신스 팝",
            lyrics="[Verse]\nhello",
            duration_seconds=60,
            prompt_output_languages=["ko", "en"],
        )
        with patch.object(music, "_request_structured_object", return_value={"contents": "warm 신스 pop"}) as request:
            result = music._enhance_music_prompt(payload)

        self.assertEqual(result.contents, "warm 신스 pop")
        self.assertEqual(request.call_args.kwargs["temperature"], 0.6)
        self.assertEqual(request.call_args.kwargs["max_tokens"], music._MUSIC_PROMPT_MAX_TOKENS)
        self.assertEqual(request.call_args.kwargs["timeout_seconds"], music._MUSIC_PROMPT_TIMEOUT_SECONDS)
        self.assertEqual(request.call_args.kwargs["name"], "music_description")
        self.assertEqual(request.call_args.kwargs["schema"]["required"], ["contents"])
        self.assertFalse(request.call_args.kwargs["schema"]["additionalProperties"])
        self.assertIn("Korean, English", request.call_args.kwargs["user_prompt"])
        self.assertIn("Rewrite the user's MiniMax-Music3 description", request.call_args.kwargs["system_prompt"])

    def test_lyrics_target_generates_from_empty_lyrics(self) -> None:
        payload = music.MusicPromptEnhancementRequest(
            target="lyrics",
            description="bright pop song",
            lyrics="",
            prompt_output_languages=["en"],
        )
        with patch.object(music, "_request_structured_object", return_value={"contents": "[Verse]\nA new day"}) as request:
            result = music._enhance_music_prompt(payload)

        self.assertEqual(result.contents, "[Verse]\nA new day")
        self.assertIn("<lyrics>\n\n</lyrics>", request.call_args.kwargs["user_prompt"])
        self.assertIn("When lyrics are empty, write complete new lyrics", request.call_args.kwargs["system_prompt"])
        self.assertEqual(request.call_args.kwargs["name"], "music_lyrics")

    def test_prompt_enhancement_rejects_duplicate_languages(self) -> None:
        with self.assertRaises(ValidationError):
            music.MusicPromptEnhancementRequest(
                target="lyrics",
                description="pop",
                prompt_output_languages=["en", "en"],
            )

    def test_korean_output_pattern_allows_standard_section_tags_only(self) -> None:
        pattern = music._music_prompt_pattern(["ko"])

        self.assertIsNotNone(re.fullmatch(pattern, "[Verse]\n새로운 아침"))
        self.assertIsNone(re.fullmatch(pattern, "ordinary English sentence"))

    def test_prompt_enhancement_error_passes_provider_response_to_audit(self) -> None:
        payload = music.MusicPromptEnhancementRequest(target="description", description="pop")
        request = Request({"type": "http", "headers": []})
        provider_response = {"choices": [{"finish_reason": "length"}]}
        with patch.object(
            music,
            "_enhance_music_prompt",
            side_effect=music._VLLMError("length", provider_response=provider_response),
        ):
            with self.assertRaises(music.HTTPException) as raised:
                music.enhance_music_prompt(payload, request, UserResponse(id=uuid4(), username="tester"))

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(request.state.provider_response, provider_response)

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
