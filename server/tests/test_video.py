import asyncio
import json
import re
import unittest
from pathlib import Path
from typing import Literal, cast
from unittest.mock import patch
from uuid import uuid4

from app import video
from app.auth import UserResponse
from app.comfyui import cancel_comfy_generation
from pydantic import ValidationError


class VideoContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user = UserResponse(id=uuid4(), username="tester")

    def test_video_workflows_use_10eros_vbvr_defaults(self) -> None:
        workflows = Path(video.__file__).with_name("workflows")
        for filename in ("video_i2v.json", "video_fl2v.json", "video_r2v.json"):
            workflow = json.loads((workflows / filename).read_text())
            unet = next(node for node in workflow.values() if node["class_type"] == "UNETLoader")
            lora_id, lora = next(
                (node_id, node) for node_id, node in workflow.items() if node["class_type"] == "LoraLoaderModelOnly"
            )
            sampler = next(node for node in workflow.values() if node["class_type"] == "KSamplerSelect")
            scheduler = next(node for node in workflow.values() if node["class_type"] == "BasicScheduler")

            self.assertEqual(unet["inputs"]["unet_name"], "MiniMaxH3/10Eros_Max_h3_TURBO-hybrid_beta4_int8_convrot.safetensors")
            self.assertEqual(lora["inputs"]["lora_name"], "MiniMax/VBVR_H3_attn_only.safetensors")
            self.assertEqual(sampler["inputs"]["sampler_name"], "res_multistep")
            self.assertEqual(scheduler["inputs"], {"model": [lora_id, 0], "scheduler": "simple", "steps": 6, "denoise": 1})

    def test_reference_markers_are_normalized_to_minimax_contract(self) -> None:
        self.assertEqual(
            video._normalize_video_reference_markers("[Image1] @video2 [Audio 3]"),
            "<Picture 1> <Video 2> <Audio 3>",
        )

    def test_cancel_running_comfy_prompt_uses_targeted_interrupt(self) -> None:
        with (
            patch("app.comfyui._request_json", return_value={"queue_running": [["item", "prompt-1"]], "queue_pending": []}),
            patch("app.comfyui._request_action") as request_action,
        ):
            self.assertTrue(cancel_comfy_generation("prompt-1"))
        request_action.assert_called_once_with("POST", "/interrupt", {"prompt_id": "prompt-1"})

    def test_cancel_pending_comfy_prompt_deletes_only_target(self) -> None:
        with (
            patch("app.comfyui._request_json", return_value={"queue_running": [], "queue_pending": [["item", "prompt-2"]]}),
            patch("app.comfyui._request_action") as request_action,
        ):
            self.assertTrue(cancel_comfy_generation("prompt-2"))
        request_action.assert_called_once_with("POST", "/queue", {"delete": ["prompt-2"]})

        requests = {
            "i2v": video.VideoGenerationRequest(
                prompt="move",
                first_frame=video.VideoAsset(kind="image", file_index=0),
            ),
            "fl2v": video.VideoGenerationRequest(
                prompt="move",
                first_frame=video.VideoAsset(kind="image", file_index=0),
                last_frame=video.VideoAsset(kind="image", file_index=1),
            ),
            "r2v": video.VideoGenerationRequest(
                prompt="move <Picture 1> <Audio 1>",
                reference_images=[video.VideoAsset(kind="image", file_index=0)],
                reference_audios=[video.VideoAsset(kind="audio", file_index=1)],
            ),
        }
        resolved = {
            "index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image"),
            "index:1": video._ResolvedAsset(file_id="b" * 32, filename="voice.wav", content=b"a", media_type="audio/wav", kind="audio"),
        }
        with patch.object(video, "_upload_to_comfy", side_effect=lambda _resolved, asset, _kind: f"{asset.file_index}.input"):
            for mode, request in requests.items():
                prompt, _ = video._build_prompt(mode, request, resolved)
                save = next(node for node in prompt.values() if node["class_type"] == "SaveVideo")
                self.assertEqual(save["inputs"]["format"], "mp4")
                self.assertEqual(save["inputs"]["codec"], "h264")
                generator = next(
                    node
                    for node in prompt.values()
                    if node["class_type"] in {"MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"}
                )
                self.assertEqual(generator["inputs"]["prompt"], request.prompt)

    def test_fps_defaults_to_24_and_reaches_video_workflow(self) -> None:
        self.assertEqual(video.VideoGenerationRequest(prompt="move").fps, 24)
        request = video.VideoGenerationRequest(
            prompt="move",
            duration=3,
            fps=30,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            prompt, _ = video._build_prompt("i2v", request, resolved)

        generator = next(node for node in prompt.values() if node["class_type"] == "MiniMaxH3ImageToVideo")
        create_video = next(node for node in prompt.values() if node["class_type"] == "CreateVideo")
        self.assertEqual(generator["inputs"]["length"], video._frame_length(3, 30))
        self.assertEqual(create_video["inputs"]["fps"], 30)

    def test_fps_validation_rejects_values_outside_supported_range(self) -> None:
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", fps=0)
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", fps=121)

    def test_duration_has_no_fixed_bounds(self) -> None:
        request = video.VideoGenerationRequest(prompt="move", duration=100)
        enhancement = video.VideoPromptEnhancementRequest(prompt="move", mode="i2v", duration=0)
        self.assertEqual(request.duration, 100)
        self.assertEqual(enhancement.duration, 0)

    def test_long_video_accepts_one_full_prompt_for_every_raw_segment(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="opening to ending",
            duration=23,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )

        self.assertEqual(video._video_segment_durations(request.duration), [10.0, 10.0, 3.0])
        self.assertEqual(video._effective_video_prompts("i2v", request), ["opening to ending"] * 3)
        with self.assertRaises(video.HTTPException):
            video._effective_video_prompts("i2v", request.model_copy(update={"segment_prompts": ["opening"]}))

    def test_continuation_queues_r2v_with_only_last_frame_reference(self) -> None:
        generation = {
            "prompt_id": "root-prompt",
            "client_id": "client-1",
            "segment_index": 0,
            "segment_durations": [10.0, 3.0],
            "segment_prompts": ["opening", "continuation"],
            "width": 768,
            "height": 1344,
            "fps": 24,
            "seed": 7,
        }
        captured: dict[str, object] = {}

        def build(mode, request, resolved, *, effective_prompt):
            captured.update(mode=mode, request=request, resolved=resolved, effective_prompt=effective_prompt)
            return {}, 7

        with (
            patch.object(video, "_build_prompt", side_effect=build),
            patch.object(video, "_request_json", return_value={"prompt_id": "r2v-prompt"}),
        ):
            prompt_id = video._queue_r2v_continuation(generation, self.user.id, "f" * 32, b"last-frame")

        request = cast(video.VideoGenerationRequest, captured["request"])
        resolved = cast(dict[str, video._ResolvedAsset], captured["resolved"])
        self.assertEqual(prompt_id, "r2v-prompt")
        self.assertEqual(captured["mode"], "r2v")
        self.assertEqual(captured["effective_prompt"], "continuation")
        self.assertEqual(request.duration, 3.0)
        self.assertEqual(request.reference_images, [video.VideoAsset(kind="image", file_id="f" * 32)])
        self.assertEqual(next(iter(resolved.values())).content, b"last-frame")

    def test_completed_segment_extracts_last_frame_before_r2v_transition(self) -> None:
        generation = {
            "prompt_id": "root-prompt",
            "active_prompt_id": None,
            "client_id": "client-1",
            "user_id": self.user.id,
            "segment_index": 0,
            "segment_durations": [10.0, 3.0],
            "segment_prompts": ["opening", "continuation"],
            "segment_file_ids": [],
            "width": 768,
            "height": 1344,
            "fps": 24,
            "seed": 7,
            "status": "processing",
        }
        with (
            patch.object(video, "claim_video_generation_segment", return_value=generation),
            patch.object(video, "_request_bytes", return_value=(b"segment-video", "video/mp4")),
            patch.object(video, "storage_upload_file", side_effect=["s" * 32, "f" * 32]),
            patch.object(video, "extract_last_video_frame", return_value=b"actual-last-frame") as extract,
            patch.object(video, "_queue_r2v_continuation", return_value="r2v-prompt") as queue,
            patch.object(video, "advance_video_generation_segment", return_value=True),
            patch.object(video, "reset_generation_progress"),
            patch.object(video, "storage_delete_file"),
        ):
            video._sync_video_output(
                generation,
                self.user.id,
                "completed-segment",
                {"save": {"videos": [{"filename": "segment.mp4", "subfolder": "", "type": "output"}]}},
            )

        extract.assert_called_once_with(content=b"segment-video", filename="segment.mp4")
        queue.assert_called_once_with(generation, self.user.id, "f" * 32, b"actual-last-frame")

    def test_completed_sequence_status_does_not_requery_comfy_history(self) -> None:
        generation = {
            "prompt_id": "root-prompt",
            "mode": "i2v",
            "status": "completed",
            "storage_file_id": "v" * 32,
            "filename": "sequence.mp4",
            "subfolder": "",
            "video_type": "output",
            "fps": 24,
            "length": 240,
            "segment_durations": [10.0, 3.0],
            "segment_index": 1,
        }
        with (
            patch.object(video, "get_video_generation", return_value=generation),
            patch.object(video, "storage_read_url", return_value="/vault/videos/root-prompt/download"),
            patch.object(video, "_request_json") as history,
        ):
            result = video._history_status(generation, self.user.id)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.progress, 100)
        self.assertEqual(result.segment_count, 2)
        history.assert_not_called()

    def test_mode_is_explicit_when_resolving_assets(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        with self.assertRaises(video.HTTPException) as context:
            asyncio.run(
                video._resolve_assets(
                    "fl2v",
                    request,
                    [],
                    self.user,
                )
            )
        self.assertEqual(context.exception.status_code, 422)

    def test_existing_media_is_downloaded_and_not_reuploaded(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            first_frame=video.VideoAsset(kind="image", file_id="a" * 32),
        )
        stored = {"file_id": "a" * 32, "filename": "image.png", "content_type": "image/png", "media_kind": "image"}
        with (
            patch.object(video, "get_reusable_media", return_value=stored),
            patch.object(video, "storage_download_file", return_value=(b"image", "image/png")),
            patch.object(video, "storage_upload_file") as upload,
            patch.object(video, "create_media_asset") as create_media,
        ):
            resolved = asyncio.run(video._resolve_assets("i2v", request, [], self.user))

        self.assertEqual(next(iter(resolved.values())).file_id, "a" * 32)
        upload.assert_not_called()
        create_media.assert_called_once()

    def test_r2v_video_connects_frames_and_audio_components(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move <Video 1>",
            reference_videos=[video.VideoAsset(kind="video", file_index=0)],
        )
        resolved = {
            "index:0": video._ResolvedAsset(file_id="a" * 32, filename="clip.mp4", content=b"video", media_type="video/mp4", kind="video"),
        }
        with patch.object(video, "_upload_to_comfy", return_value="clip.mp4"):
            prompt, _ = video._build_prompt("r2v", request, resolved)

        self.assertEqual(prompt["300"], {"class_type": "LoadVideo", "inputs": {"file": "clip.mp4"}})
        self.assertEqual(prompt["400"]["inputs"], {"video": ["300", 0]})
        self.assertEqual(prompt["5"]["inputs"]["ref_videos.ref_video_0"], ["400", 0])
        self.assertEqual(prompt["5"]["inputs"]["ref_video_audios.ref_video_audio_0"], ["400", 1])

    def test_audio_input_uses_comfyui_common_upload_route(self) -> None:
        source = video._ResolvedAsset(
            file_id="a" * 32,
            filename="voice.wav",
            content=b"audio",
            media_type="audio/wav",
            kind="audio",
        )

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"name":"voice.wav"}'

        with (
            patch.object(video, "_comfy_url", side_effect=lambda endpoint: f"http://comfy.local{endpoint}"),
            patch.object(video, "urlopen", return_value=Response()) as open_url,
        ):
            result = video._upload_to_comfy({"index:0": source}, video.VideoAsset(kind="audio", file_index=0), "audio")

        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://comfy.local/upload/image")
        self.assertIn(b'name="image"', request.data)
        self.assertNotIn(b'name="audio"', request.data)
        self.assertEqual(result, "voice.wav")

    def test_video_input_has_video_fallback_suffix(self) -> None:
        source = video._ResolvedAsset(
            file_id="a" * 32,
            filename="clip",
            content=b"video",
            media_type="video/mp4",
            kind="video",
        )

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"name":"clip.mp4"}'

        with (
            patch.object(video, "_comfy_url", side_effect=lambda endpoint: f"http://comfy.local{endpoint}"),
            patch.object(video, "urlopen", return_value=Response()) as open_url,
        ):
            video._upload_to_comfy({"index:0": source}, video.VideoAsset(kind="video", file_index=0), "video")

        request = open_url.call_args.args[0]
        self.assertIn(b'filename="local_field_', request.data)
        self.assertIn(b".mp4", request.data)

    def test_video_prompt_pattern_is_language_union_with_digits_and_symbols(self) -> None:
        korean_labels = video._video_prompt_section_labels(["ko"])
        korean_prompt = "\n".join(f"{label}\n장면 0초-3초 @image1: !?" for label in korean_labels)
        self.assertIsNotNone(re.fullmatch(video._video_prompt_pattern(["ko"]), korean_prompt))
        self.assertIsNone(re.fullmatch(video._video_prompt_pattern(["ko"]), korean_prompt.replace("장면", "scene", 1)))

        mixed_labels = video._video_prompt_section_labels(["ko", "en"])
        mixed_prompt = "\n".join(f"{label}\nred 빨강 16:9 @image1: !?" for label in mixed_labels)
        self.assertIsNotNone(re.fullmatch(video._video_prompt_pattern(["ko", "en"]), mixed_prompt))

        japanese_labels = video._video_prompt_section_labels(["ja"])
        japanese_prompt = "\n".join(f"{label}\n動き 0秒-3秒 @image1: !?" for label in japanese_labels)
        self.assertIsNotNone(re.fullmatch(video._video_prompt_pattern(["ja"]), japanese_prompt))
        self.assertIsNone(re.fullmatch(video._video_prompt_pattern(["ja"]), japanese_prompt.replace("動き", "move", 1)))

    def test_video_prompt_requires_atlas_six_blocks_in_order(self) -> None:
        labels = video._video_prompt_section_labels(["en"])
        valid = "\n".join(f"{label}\nA concrete instruction." for label in labels)
        self.assertEqual(video._validate_video_prompt_contents(valid, ["en"]), valid)
        with self.assertRaises(video._VLLMError):
            video._validate_video_prompt_contents(valid.replace("Negative:", "Text:", 1), ["en"])

    def test_video_prompt_enhancement_uses_selected_languages_and_pattern(self) -> None:
        languages: list[Literal["ko", "en", "ja"]] = ["ko", "en"]
        fields = {field: f"red 빨강 0s-5s @image1: !?" for field in video._VIDEO_PROMPT_FIELDS}
        payload = video.VideoPromptEnhancementRequest(
            prompt="사과가 움직인다",
            mode="i2v",
            duration=5,
            prompt_output_languages=languages,
        )
        with patch.object(video, "_request_structured_object", return_value=fields) as request:
            result = video._enhance_video_prompt(payload)

        expected = video._assemble_video_prompt(
            {field: video._normalize_video_reference_markers(value) for field, value in fields.items()},
            languages,
        )
        self.assertEqual(result.improved_prompt.contents, expected)
        self.assertEqual(request.call_args.kwargs["temperature"], 0.8)
        self.assertEqual(request.call_args.kwargs["name"], "video_prompt_fields")
        schema = request.call_args.kwargs["schema"]
        self.assertEqual(set(schema["required"]), set(video._VIDEO_PROMPT_FIELDS))
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(schema["properties"]["style"]["pattern"], video._video_prompt_pattern(languages))
        self.assertIn("Korean, English", request.call_args.kwargs["user_prompt"])

    def test_sequence_enhancement_uses_zero_based_local_timeline_clock(self) -> None:
        fields = {field: "concrete 0s-1s instruction" for field in video._VIDEO_PROMPT_FIELDS}
        payload = video.VideoPromptEnhancementRequest(
            prompt="continue the scene",
            mode="r2v",
            duration=1,
            segment_index=1,
            segment_count=2,
            previous_segment_prompt="opening 0s-10s",
            prompt_output_languages=["en"],
        )
        with patch.object(video, "_request_structured_object", return_value=fields) as request:
            video._enhance_video_prompt(payload)

        system_prompt = request.call_args.kwargs["system_prompt"]
        user_prompt = request.call_args.kwargs["user_prompt"]
        self.assertIn("The supplied user prompt describes the full sequence", system_prompt)
        self.assertIn("local timeline from 0s to the supplied duration", system_prompt)
        self.assertIn("<duration_seconds>\n1\n</duration_seconds>", user_prompt)
        self.assertIn("<sequence_segment>\n2/2\n</sequence_segment>", user_prompt)
        self.assertIn("<timeline_clock>\n0s to 1s", user_prompt)

    def test_enabled_video_enhancement_adds_reference_roles_to_workflow_prompt(self) -> None:
        labels = video._video_prompt_section_labels(["en"])
        improved = "\n".join(f"{label}\nconcrete instruction 0s-5s @image1: !?" for label in labels)
        request = video.VideoGenerationRequest(
            prompt="move",
            prompt_enhancement_enabled=True,
            improved_prompt=improved,
            prompt_output_languages=["en"],
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        effective = video._effective_video_prompt("i2v", request)
        self.assertIn("<Picture 1>: start-image reference", effective)
        normalized_improved = video._normalize_video_reference_markers(improved)
        self.assertIn(normalized_improved, effective)

    def test_duplicate_video_prompt_languages_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", prompt_output_languages=["en", "en"])


if __name__ == "__main__":
    unittest.main()
