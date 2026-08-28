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

    def test_unknown_value_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PresetCreateRequest.model_validate({"type": "t2i", "name": "portrait", "values": {"unknown": "value"}})

    def test_only_t2i_type_is_supported(self) -> None:
        with self.assertRaises(ValidationError):
            PresetCreateRequest.model_validate({"type": "i2v", "name": "portrait", "values": {"prompt": "a portrait"}})


if __name__ == "__main__":
    unittest.main()
