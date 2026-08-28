from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import generation_worker, video


class GenerationWorkerTest(unittest.TestCase):
    def test_reconciler_processes_active_images_and_videos(self) -> None:
        image_user = uuid4()
        video_user = uuid4()
        image = {"prompt_id": "image-prompt", "user_id": image_user}
        video_generation = {"prompt_id": "video-prompt", "user_id": video_user}
        with (
            patch.object(generation_worker, "list_active_image_generations", return_value=[image]),
            patch.object(generation_worker, "list_active_video_generations", return_value=[video_generation]),
            patch.object(generation_worker, "_history_generation_status") as image_sync,
            patch.object(generation_worker, "_history_status") as video_sync,
        ):
            generation_worker.reconcile_active_generations()

        image_sync.assert_called_once_with("image-prompt", image_user)
        video_sync.assert_called_once_with(video_generation, video_user)

    def test_video_sse_emits_completed_from_server_state(self) -> None:
        user_id = uuid4()
        generation = {
            "prompt_id": "video-prompt",
            "mode": "i2v",
            "status": "completed",
            "storage_file_id": "file-id",
            "filename": "result.mp4",
            "subfolder": "",
            "video_type": "output",
        }
        output = video.VideoOutput(url="https://storage.example/result.mp4", filename="result.mp4", subfolder="", type="output")

        async def first_event() -> str:
            events = video._stream_video_events("video-prompt", "i2v", user_id)
            return await anext(events)

        with (
            patch.object(video, "get_video_generation", return_value=generation),
            patch.object(video, "_video_output", return_value=output),
        ):
            event = asyncio.run(first_event())

        self.assertIn("event: completed", event)
        payload = json.loads(event.split("data: ", 1)[1].strip())
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["video"]["url"], output.url)


if __name__ == "__main__":
    unittest.main()
