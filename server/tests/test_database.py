import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from app import database


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, query: str, parameters: tuple[object, ...]) -> None:
        self.calls.append((query, parameters))


class VideoGenerationStatusTest(unittest.TestCase):
    def test_nullable_media_metadata_is_typed_and_preserved(self) -> None:
        connection = FakeConnection()
        user_id = uuid4()

        with patch.object(database, "get_connection", return_value=connection):
            database.update_video_generation_status(
                prompt_id="video-prompt",
                user_id=user_id,
                status="processing",
            )

        query, parameters = connection.calls[0]
        self.assertIn("subfolder = COALESCE(%s::varchar, subfolder)", query)
        self.assertIn("video_type = COALESCE(%s::varchar, video_type)", query)
        self.assertIn("elapsed_seconds = GREATEST", query)
        self.assertEqual(parameters[3:5], (None, None))

    def test_completed_media_metadata_is_written(self) -> None:
        connection = FakeConnection()
        user_id = uuid4()

        with patch.object(database, "get_connection", return_value=connection):
            database.update_video_generation_status(
                prompt_id="video-prompt",
                user_id=user_id,
                status="completed",
                filename="result.mp4",
                subfolder="renders",
                video_type="output",
            )

        _, parameters = connection.calls[0]
        self.assertEqual(parameters[3:5], ("renders", "output"))

    def test_active_elapsed_seconds_is_derived_from_created_at(self) -> None:
        elapsed = database.generation_elapsed_seconds(
            {
                "status": "processing",
                "created_at": datetime.now(timezone.utc) - timedelta(seconds=2),
                "elapsed_seconds": 0,
            }
        )
        self.assertGreaterEqual(elapsed, 2)


if __name__ == "__main__":
    unittest.main()
