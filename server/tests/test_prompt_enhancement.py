import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.comfyui import (
    ImageGenerationRequest,
    _MAX_SEED,
    _build_prompt,
    _effective_positive_prompt,
    _enhance_prompt,
    _request_structured_content,
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

    def test_seed_above_postgres_bigint_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ImageGenerationRequest(
                prompt="a red apple",
                checkpoint="Anima/test.safetensors",
                seed=_MAX_SEED + 1,
            )

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

    def test_enhancement_does_not_prefix_original_prompt(self) -> None:
        with (
            patch("app.comfyui.search_danbooru_tags", return_value=["solo", "still_life"]),
            patch("app.comfyui._request_structured_content", side_effect=["soft studio lighting", "solo, still_life"]) as request,
            patch("app.comfyui.validate_danbooru_tags", return_value=["solo", "still_life"]),
        ):
            result = _enhance_prompt("a red apple")

        self.assertEqual(result.improved_prompt.contents, "solo, still_life, soft studio lighting")
        self.assertEqual([call.kwargs["temperature"] for call in request.call_args_list], [0.8, 0.8])
        self.assertNotIn("English", IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT)
        self.assertNotIn("English", IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT)

    def test_structured_output_uses_the_allowed_character_pattern(self) -> None:
        with patch(
            "app.comfyui._request_vllm_json",
            return_value={"choices": [{"finish_reason": "stop", "message": {"content": '{"contents":"a red apple"}'}}]},
        ) as request:
            _request_structured_content(system_prompt="system", user_prompt="user", max_tokens=64, temperature=0.8)

        contents = request.call_args.args[0]["response_format"]["json_schema"]["schema"]["properties"]["contents"]
        self.assertEqual(contents["pattern"], r"^[A-Za-z0-9 ,'-]+$")


if __name__ == "__main__":
    unittest.main()
