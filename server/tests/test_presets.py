import unittest

from pydantic import ValidationError

from app.presets import PresetCreateRequest, PresetUpdateRequest, PresetValues


class PresetRequestTest(unittest.TestCase):
    def test_request_keeps_only_selected_values(self) -> None:
        payload = PresetCreateRequest(
            type="t2i_anima",
            name="  portrait  ",
            values=PresetValues(prompt="a portrait", cfg=5),
        )

        self.assertEqual(payload.name, "portrait")
        self.assertEqual(payload.values.model_dump(exclude_none=True), {"prompt": "a portrait", "cfg": 5.0})

    def test_default_flag_is_supported(self) -> None:
        create_payload = PresetCreateRequest(
            type="t2i_anima",
            name="portrait",
            values=PresetValues(prompt="a portrait"),
            is_default=True,
        )
        update_payload = PresetUpdateRequest(
            type="t2i_anima",
            name="portrait",
            values=PresetValues(prompt="a portrait"),
            is_default=False,
        )

        self.assertTrue(create_payload.is_default)
        self.assertFalse(update_payload.is_default)
        self.assertEqual(update_payload.type, "t2i_anima")

    def test_unknown_value_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PresetCreateRequest.model_validate({"type": "t2i_anima", "name": "portrait", "values": {"unknown": "value"}})

    def test_image_and_video_types_are_supported(self) -> None:
        payload = PresetCreateRequest(
            type="video",
            name="  motion  ",
            values=PresetValues.model_validate(
                {
                    "prompt": "a moving portrait",
                    "mode": "i2v",
                    "width": 1344,
                    "height": 768,
                    "duration": 100,
                    "loras": [{"name": "style.safetensors", "strength": -100}],
                    "random_seed": True,
                }
            ),
        )

        self.assertEqual(payload.type, "video")
        self.assertEqual(payload.values.mode, "i2v")
        self.assertEqual(payload.values.duration, 100)
        self.assertEqual(payload.values.loras[0].strength, -100)

    def test_image_preset_accepts_sampler_scheduler_and_seed(self) -> None:
        payload = PresetCreateRequest.model_validate(
            {
                "type": "t2i_illustrious",
                "name": "sampling",
                "values": {"sampler_name": "euler", "scheduler": "normal", "seed": "123"},
            }
        )
        self.assertEqual(payload.values.sampler_name, "euler")
        self.assertEqual(payload.values.scheduler, "normal")
        self.assertEqual(payload.values.seed, "123")

    def test_all_image_namespaces_are_accepted(self) -> None:
        preset_types = ("t2i_anima", "i2i_anima", "t2i_illustrious", "i2i_illustrious", "t2i_krea2", "i2i_krea2")
        payload_types = [
            PresetCreateRequest.model_validate({"type": preset_type, "name": preset_type, "values": {"prompt": "portrait"}}).type
            for preset_type in preset_types
        ]
        self.assertEqual(payload_types, list(preset_types))

    def test_unknown_type_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PresetCreateRequest.model_validate({"type": "i2v", "name": "portrait", "values": {"prompt": "a portrait"}})


if __name__ == "__main__":
    unittest.main()
