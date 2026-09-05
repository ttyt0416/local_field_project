import json
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

    def execute(self, query: str, parameters: tuple[object, ...]) -> object:
        self.calls.append((query, parameters))


class ReturningCursor:
    def __init__(self, row: tuple[object, ...]) -> None:
        self.row = row

    def fetchone(self) -> tuple[object, ...]:
        return self.row


class ReturningConnection(FakeConnection):
    def __init__(self, row: tuple[object, ...]) -> None:
        super().__init__()
        self.row = row

    def execute(self, query: str, parameters: tuple[object, ...]) -> ReturningCursor:
        self.calls.append((query, parameters))
        return ReturningCursor(self.row)


class RowsCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class RowsConnection(FakeConnection):
    def execute(self, query: str, parameters: tuple[object, ...]) -> RowsCursor:
        self.calls.append((query, parameters))
        return RowsCursor([])


class VideoGenerationStatusTest(unittest.TestCase):
    def test_model_download_active_filter_is_explicit(self) -> None:
        connection = RowsConnection()
        with patch.object(database, "get_connection", return_value=connection):
            database.list_model_downloads(uuid4(), active_only=True)

        self.assertIn("status IN ('queued', 'downloading')", connection.calls[0][0])

    def test_shared_generation_storage_reference_excludes_snapshot_ids(self) -> None:
        connection = ReturningConnection((True,))
        user_id = uuid4()
        generation_ids = [uuid4()]
        with patch.object(database, "get_connection", return_value=connection):
            result = database.has_generation_storage_reference_outside("file-1", user_id, generation_ids)

        self.assertTrue(result)
        self.assertIn("image_generations", connection.calls[0][0])
        self.assertIn("source_file_id", connection.calls[0][0])
        self.assertIn("video_generations", connection.calls[0][0])
        parameters = connection.calls[0][1]
        self.assertEqual(parameters[0:2], ("file-1", "file-1"))
        self.assertEqual(parameters[3], generation_ids)
        self.assertEqual(parameters[6], generation_ids)
        self.assertEqual(parameters[10], generation_ids)

    def test_create_image_generation_reads_returning_cursor(self) -> None:
        generation_id = uuid4()
        created_at = datetime.now(timezone.utc)
        connection = ReturningConnection((generation_id, created_at))

        with patch.object(database, "get_connection", return_value=connection):
            result = database.create_image_generation(
                user_id=uuid4(),
                prompt_id="image-prompt",
                client_id="image-client",
                prompt="prompt",
                negative_prompt="",
                checkpoint="checkpoint",
                loras=[],
                cfg=7,
                steps=20,
                width=512,
                height=512,
                seed=1,
            )

        self.assertEqual(result, (generation_id, created_at))

    def test_create_image_edit_copies_source_and_overrides_media_metadata(self) -> None:
        edited_id = uuid4()
        connection = ReturningConnection((edited_id,))
        user_id = uuid4()
        source_id = uuid4()

        with patch.object(database, "get_connection", return_value=connection):
            result = database.create_image_edit(
                user_id=user_id,
                source_generation_id=source_id,
                storage_file_id="edited-file",
                filename="edited.png",
                width=256,
                height=128,
                elapsed_seconds=0,
            )

        query, parameters = connection.calls[0]
        self.assertEqual(result, edited_id)
        self.assertIn("source_generation_id, is_edited", query)
        self.assertEqual(parameters[-2:], (source_id, user_id))

    def test_create_video_edit_copies_source_and_overrides_media_metadata(self) -> None:
        edited_id = uuid4()
        connection = ReturningConnection((edited_id,))
        user_id = uuid4()
        source_id = uuid4()

        with patch.object(database, "get_connection", return_value=connection):
            result = database.create_video_edit(
                user_id=user_id,
                source_generation_id=source_id,
                storage_file_id="edited-file",
                filename="edited.mp4",
                width=256,
                height=128,
                length=12,
                elapsed_seconds=1.2,
            )

        query, parameters = connection.calls[0]
        self.assertEqual(result, edited_id)
        self.assertIn("source_generation_id, is_edited", query)
        self.assertEqual(parameters[-2:], (source_id, user_id))

    def test_create_video_generation_reads_returning_cursor(self) -> None:
        generation_id = uuid4()
        created_at = datetime.now(timezone.utc)
        connection = ReturningConnection((generation_id, created_at))

        with patch.object(database, "get_connection", return_value=connection):
            result = database.create_video_generation(
                user_id=uuid4(),
                prompt_id="video-prompt",
                client_id="video-client",
                mode="r2v",
                prompt="prompt",
                checkpoint="MiniMaxH3/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                width=512,
                height=512,
                length=120,
                fps=24,
                seed=1,
                input_file_ids=[],
                input_segment_prompts=["input 1", "input 2"],
                improved_segment_prompts=["improved 1", "improved 2"],
                continuation_mode="i2v",
                reference_image_file_ids=["a" * 32],
            )

        self.assertEqual(result, (generation_id, created_at))
        query, parameters = connection.calls[0]
        self.assertIn("input_segment_prompts, improved_segment_prompts", query)
        self.assertEqual(parameters[6], "MiniMaxH3/minimax_h3_ref2va_pruned_int8_convrot.safetensors")
        self.assertEqual(json.loads(str(parameters[7])), [])
        self.assertEqual(json.loads(str(parameters[16])), ["input 1", "input 2"])
        self.assertEqual(json.loads(str(parameters[17])), ["improved 1", "improved 2"])
        self.assertEqual(parameters[19], "i2v")
        self.assertEqual(json.loads(str(parameters[20])), ["a" * 32])

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
