import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.configs.constants import DEFAULT_VLLM_MODEL, settings
from app.comfyui import (
    ImageGenerationRequest,
    _MAX_SEED,
    _build_prompt,
    _effective_positive_prompt,
    _enhance_prompt,
    _request_structured_content,
    _request_structured_object,
    _VLLMError,
)
from app.prompts import IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT, IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT


class PromptEnhancementTest(unittest.TestCase):
    def test_disabled_enhancement_keeps_original_prompt(self) -> None:
        payload = ImageGenerationRequest(prompt="a red apple", checkpoint="Anima/test.safetensors")
        self.assertEqual(_effective_positive_prompt(payload), "a red apple")

    def test_generated_seed_fits_postgres_bigint(self) -> None:
        payload = ImageGenerationRequest(prompt="a red apple", checkpoint="Anima/test.safetensors")
        with patch("app.comfyui.secrets.randbelow", return_value=_MAX_SEED):
            _, seed = _build_prompt(payload)
        self.assertEqual(seed, _MAX_SEED)

    def test_sampler_and_scheduler_are_written_to_workflow(self) -> None:
        payload = ImageGenerationRequest(
            prompt="a red apple",
            checkpoint="Anima/test.safetensors",
            sampler_name="euler",
            scheduler="normal",
        )
        workflow, _ = _build_prompt(payload)
        sampler = next(node for node in workflow.values() if node["class_type"] == "KSampler")
        self.assertEqual(sampler["inputs"]["sampler_name"], "euler")
        self.assertEqual(sampler["inputs"]["scheduler"], "normal")

    def test_seed_above_postgres_bigint_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ImageGenerationRequest(
                prompt="a red apple",
                checkpoint="Anima/test.safetensors",
                seed=_MAX_SEED + 1,
            )

    def test_lora_strength_has_no_fixed_bounds(self) -> None:
        payload = ImageGenerationRequest.model_validate(
            {
                "prompt": "a red apple",
                "checkpoint": "Anima/test.safetensors",
                "loras": [{"name": "style.safetensors", "strength": -100}],
            }
        )
        self.assertEqual(payload.loras[0].strength, -100)

    def test_enabled_enhancement_uses_one_improved_prompt(self) -> None:
        payload = ImageGenerationRequest(
            prompt="a red apple",
            prompt_enhancement_enabled=True,
            improved_prompt="solo, still_life, soft studio lighting",
            checkpoint="Anima/test.safetensors",
        )
        self.assertEqual(
            _effective_positive_prompt(payload),
            "solo, still_life, soft studio lighting",
        )

    def test_anima_enhancement_keeps_tags_and_natural_language(self) -> None:
        with (
            patch("app.comfyui.search_danbooru_tags", return_value=["solo", "still_life"]),
            patch("app.comfyui._request_structured_content", side_effect=["soft studio lighting", "solo, still_life"]) as request,
            patch("app.comfyui.validate_danbooru_tags", return_value=["solo", "still_life"]),
        ):
            result = _enhance_prompt("a red apple", "anima")

        self.assertEqual(result.improved_prompt.contents, "solo, still_life, soft studio lighting")
        self.assertEqual([call.kwargs["temperature"] for call in request.call_args_list], [0.6, 0.6])
        self.assertNotIn("English", IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT)
        self.assertNotIn("English", IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT)

    def test_illustrious_enhancement_returns_danbooru_tags_only(self) -> None:
        with (
            patch("app.comfyui.search_danbooru_tags", return_value=["solo", "still_life"]),
            patch("app.comfyui._request_structured_content", return_value="solo, still_life") as request,
            patch("app.comfyui.validate_danbooru_tags", return_value=["solo", "still_life"]),
        ):
            result = _enhance_prompt("a red apple", "illustrious")

        self.assertEqual(result.improved_prompt.contents, "solo, still_life")
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs["system_prompt"], IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT)
        self.assertEqual(request.call_args.kwargs["temperature"], 0.6)

    def test_krea_enhancement_uses_prompt_temperature(self) -> None:
        with patch("app.comfyui._request_structured_content", return_value="soft studio lighting") as request:
            result = _enhance_prompt("a red apple", "krea2")

        self.assertEqual(result.improved_prompt.contents, "soft studio lighting")
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs["temperature"], 0.6)

    def test_structured_output_uses_the_allowed_character_pattern(self) -> None:
        with patch(
            "app.comfyui._request_vllm_json",
            return_value={"choices": [{"finish_reason": "stop", "message": {"content": '{"contents":"a red apple"}'}}]},
        ) as request:
            _request_structured_content(system_prompt="system", user_prompt="user", max_tokens=64, temperature=0.8)

        contents = request.call_args.args[0]["response_format"]["json_schema"]["schema"]["properties"]["contents"]
        self.assertEqual(contents["pattern"], r"^[A-Za-z0-9 ,'-]+$")

    def test_structured_enhancement_uses_shared_target_model(self) -> None:
        self.assertEqual(DEFAULT_VLLM_MODEL, "pekkAi/G4-MeroMero-26B-A4B-it-uncensored-heretic-NVFP4")
        response = {"choices": [{"finish_reason": "stop", "message": {"content": '{"contents":"a red apple"}'}}]}
        with patch("app.comfyui._request_vllm_json", return_value=response) as request:
            _request_structured_content(system_prompt="system", user_prompt="user", max_tokens=64, temperature=0.8)

        self.assertEqual(request.call_args.args[0]["model"], settings.vllm_model)

    def test_structured_length_logs_safe_video_metadata(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "shots": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"timeline": {"type": "string"}}},
                }
            },
        }
        response = {
            "usage": {"completion_tokens": 1024},
            "choices": [{"finish_reason": "length", "message": {"content": '{"shots":[{"timeline":"private action'}}],
        }
        with patch("app.comfyui._request_vllm_json", return_value=response):
            with self.assertLogs("app.comfyui", level="WARNING") as logs:
                with self.assertRaisesRegex(_VLLMError, "길이 제한") as raised:
                    _request_structured_object(
                        system_prompt="system",
                        user_prompt="user",
                        max_tokens=1024,
                        temperature=0.3,
                        schema=schema,
                        name="video_prompt_shots",
                    )

        line = logs.output[-1]
        self.assertEqual(raised.exception.provider_response, response)
        self.assertIn("name=video_prompt_shots", line)
        self.assertIn("completion_tokens=1024", line)
        self.assertIn("json_complete=False", line)
        self.assertIn("last_field=timeline", line)
        self.assertNotIn("private action", line)


if __name__ == "__main__":
    unittest.main()
