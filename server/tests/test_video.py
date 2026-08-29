import asyncio
import re
import unittest
from typing import Literal
from unittest.mock import patch
from uuid import uuid4

from app import video
from app.auth import UserResponse
from pydantic import ValidationError


class VideoContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user = UserResponse(id=uuid4(), username="tester")

    def test_each_mode_uses_its_own_workflow_and_dynamic_save_video_format(self) -> None:
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

        expected = video._assemble_video_prompt(fields, languages)
        self.assertEqual(result.improved_prompt.contents, expected)
        self.assertEqual(request.call_args.kwargs["temperature"], 0.8)
        self.assertEqual(request.call_args.kwargs["name"], "video_prompt_fields")
        schema = request.call_args.kwargs["schema"]
        self.assertEqual(set(schema["required"]), set(video._VIDEO_PROMPT_FIELDS))
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(schema["properties"]["style"]["pattern"], video._video_prompt_pattern(languages))
        self.assertIn("Korean, English", request.call_args.kwargs["user_prompt"])

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
        self.assertIn("@image1: start-image reference", effective)
        self.assertIn(improved, effective)

    def test_duplicate_video_prompt_languages_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", prompt_output_languages=["en", "en"])


if __name__ == "__main__":
    unittest.main()
