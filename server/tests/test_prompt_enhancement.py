import unittest

from app.comfyui import ImageGenerationRequest, _effective_positive_prompt


class PromptEnhancementTest(unittest.TestCase):
    def test_disabled_enhancement_keeps_original_prompt(self) -> None:
        payload = ImageGenerationRequest(prompt="a red apple", checkpoint="Anima/test.safetensors")
        self.assertEqual(_effective_positive_prompt(payload), "a red apple")

    def test_enabled_enhancement_combines_editable_contents(self) -> None:
        payload = ImageGenerationRequest(
            prompt="a red apple",
            prompt_enhancement_enabled=True,
            enhanced_natural_language_prompt="soft studio lighting",
            enhanced_danbooru_prompt="solo, still_life",
            checkpoint="Anima/test.safetensors",
        )
        self.assertEqual(
            _effective_positive_prompt(payload),
            "a red apple, solo, still_life, soft studio lighting",
        )


if __name__ == "__main__":
    unittest.main()
