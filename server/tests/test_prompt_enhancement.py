import unittest
from unittest.mock import patch

from app.comfyui import ImageGenerationRequest, _effective_positive_prompt, _enhance_prompt


class PromptEnhancementTest(unittest.TestCase):
    def test_disabled_enhancement_keeps_original_prompt(self) -> None:
        payload = ImageGenerationRequest(prompt="a red apple", checkpoint="Anima/test.safetensors")
        self.assertEqual(_effective_positive_prompt(payload), "a red apple")

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
            patch("app.comfyui._request_structured_content", side_effect=["soft studio lighting", "solo, still_life"]),
            patch("app.comfyui.validate_danbooru_tags", return_value=["solo", "still_life"]),
        ):
            result = _enhance_prompt("a red apple")

        self.assertEqual(result.improved_prompt.contents, "solo, still_life, soft studio lighting")


if __name__ == "__main__":
    unittest.main()
