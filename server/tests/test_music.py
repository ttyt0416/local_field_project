import unittest

from app import database, music
from app.auth import UserResponse
from uuid import uuid4


class MusicContractTest(unittest.TestCase):
    def test_options_exposes_local_music3_service_gate(self) -> None:
        options = music.music_options(UserResponse(id=uuid4(), username="tester"))

        self.assertEqual(options.model, "MiniMax-Music3")
        self.assertFalse(options.service_available)
        self.assertIn("연결 전", options.detail)

    def test_schema_reserves_durable_music_generation_fields(self) -> None:
        schema = "\n".join(database._SCHEMA_STATEMENTS)

        self.assertIn("CREATE TABLE IF NOT EXISTS music_generations", schema)
        for field in ("prompt_id", "client_id", "description", "lyrics", "seed", "storage_file_id", "duration_seconds", "size_bytes"):
            self.assertIn(field, schema)


if __name__ == "__main__":
    unittest.main()
