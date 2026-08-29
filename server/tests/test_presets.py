import unittest

from pydantic import ValidationError

from app.presets import PresetCreateRequest, PresetUpdateRequest, PresetValues


class PresetRequestTest(unittest.TestCase):
    def test_request_keeps_only_selected_values(self) -> None:
        payload = PresetCreateRequest(
            type="t2i",
            name="  portrait  ",
            values=PresetValues(prompt="a portrait", cfg=5),
        )

        self.assertEqual(payload.name, "portrait")
        self.assertEqual(payload.values.model_dump(exclude_none=True), {"prompt": "a portrait", "cfg": 5.0})

    def test_default_flag_is_supported(self) -> None:
        create_payload = PresetCreateRequest(
            type="t2i",
            name="portrait",
            values=PresetValues(prompt="a portrait"),
            is_default=True,
        )
        update_payload = PresetUpdateRequest(
            name="portrait",
            values=PresetValues(prompt="a portrait"),
            is_default=False,
        )

        self.assertTrue(create_payload.is_default)
        self.assertFalse(update_payload.is_default)
        self.assertEqual(update_payload.type, "t2i")

    def test_unknown_value_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PresetCreateRequest.model_validate({"type": "t2i", "name": "portrait", "values": {"unknown": "value"}})

    def test_image_and_video_types_are_supported(self) -> None:
        payload = PresetCreateRequest(
            type="video",
            name="  motion  ",
            values=PresetValues(prompt="a moving portrait", mode="i2v", width=1344, height=768, duration=5, random_seed=True),
        )

        self.assertEqual(payload.type, "video")
        self.assertEqual(payload.values.mode, "i2v")

    def test_unknown_type_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PresetCreateRequest.model_validate({"type": "i2v", "name": "portrait", "values": {"prompt": "a portrait"}})


if __name__ == "__main__":
    unittest.main()
