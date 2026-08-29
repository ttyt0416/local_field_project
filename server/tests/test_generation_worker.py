from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import comfyui, generation_worker, video
from app.generation_events import GenerationEventBroker, generation_event_broker, generation_key


class GenerationWorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        generation_worker._last_published_signatures.clear()

    def test_reconciler_processes_active_images_and_videos_and_publishes_changes(self) -> None:
        image_user = uuid4()
        video_user = uuid4()
        image = {"prompt_id": "image-prompt", "user_id": image_user, "status": "queued"}
        video_generation = {"prompt_id": "video-prompt", "user_id": video_user, "status": "queued", "mode": "i2v"}
        image_result = comfyui.ImageGenerationStatus(prompt_id="image-prompt", status="processing", progress=37)
        video_result = video.VideoGenerationStatus(prompt_id="video-prompt", mode="i2v", status="processing", progress=42)
        with (
            patch.object(generation_worker, "list_active_image_generations", return_value=[image]),
            patch.object(generation_worker, "list_active_video_generations", return_value=[video_generation]),
            patch.object(generation_worker, "_history_generation_status", return_value=image_result) as image_sync,
            patch.object(generation_worker, "_history_status", return_value=video_result) as video_sync,
            patch.object(generation_worker.generation_event_broker, "publish") as publish,
        ):
            generation_worker.reconcile_active_generations()

        image_sync.assert_called_once_with("image-prompt", image_user)
        video_sync.assert_called_once_with(video_generation, video_user)
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(publish.call_args_list[0].kwargs["event"], "status")
        self.assertEqual(publish.call_args_list[1].kwargs["event"], "status")
        self.assertEqual(publish.call_args_list[0].kwargs["data"]["progress"], 37)
        self.assertEqual(publish.call_args_list[1].kwargs["data"]["progress"], 42)

    def test_publishes_when_progress_changes_without_status_change(self) -> None:
        user_id = uuid4()
        generation = {"prompt_id": "progress-prompt", "user_id": user_id, "status": "processing"}
        with patch.object(generation_worker.generation_event_broker, "publish") as publish:
            generation_worker._publish_if_changed(
                "video", generation, "processing", "processing", {"progress": 10}
            )
            generation_worker._publish_if_changed(
                "video", generation, "processing", "processing", {"progress": 20}
            )
            generation_worker._publish_if_changed(
                "video", generation, "processing", "processing", {"progress": 20}
            )

        self.assertEqual(publish.call_count, 2)
        self.assertEqual(publish.call_args_list[0].kwargs["data"]["progress"], 10)
        self.assertEqual(publish.call_args_list[1].kwargs["data"]["progress"], 20)

    def test_records_comfy_progress_for_shared_image_and_video_status_contract(self) -> None:
        user_id = uuid4()
        self.assertTrue(
            comfyui.record_comfy_progress(
                "progress-prompt", user_id, "execution_start", {"prompt_id": "progress-prompt"}
            )
        )
        self.assertTrue(
            comfyui.record_comfy_progress(
                "progress-prompt", user_id, "progress", {"prompt_id": "progress-prompt", "value": 25, "max": 100}
            )
        )
        self.assertFalse(
            comfyui.record_comfy_progress(
                "progress-prompt", user_id, "progress", {"prompt_id": "progress-prompt", "value": 25, "max": 100}
            )
        )
        self.assertEqual(
            comfyui.generation_progress("progress-prompt", user_id),
            {"status": "processing", "progress": 25.0, "queue_position": None},
        )

    def test_comfy_progress_websocket_uses_client_id_query(self) -> None:
        self.assertEqual(
            comfyui._comfy_websocket_url("client id"),
            "ws://host.docker.internal:8188/ws?clientId=client+id",
        )

    def test_broker_pushes_events_to_a_generation_subscriber(self) -> None:
        async def receive() -> dict[str, object]:
            broker = GenerationEventBroker()
            async with broker.subscribe("image:user:prompt") as queue:
                broker.publish(key="image:user:prompt", event="status", data={"status": "processing"})
                return await asyncio.wait_for(queue.get(), timeout=1)

        message = asyncio.run(receive())
        self.assertEqual(message["event"], "status")
        self.assertEqual(message["data"], {"status": "processing"})

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

    def test_image_sse_receives_worker_push_without_polling(self) -> None:
        user_id = uuid4()
        generation = {"prompt_id": "image-prompt", "client_id": "image-client", "status": "queued"}

        async def receive_push() -> tuple[str, str]:
            events = comfyui._stream_generation_events("image-prompt", "image-client", user_id)
            first = await anext(events)
            next_event = asyncio.create_task(anext(events))
            await asyncio.sleep(0)
            generation_event_broker.publish(
                key=generation_key("image", user_id, "image-prompt"),
                event="completed",
                data={"prompt_id": "image-prompt", "status": "completed", "images": []},
            )
            second = await asyncio.wait_for(next_event, timeout=1)
            return first, second

        with patch.object(comfyui, "get_image_generation", return_value=generation) as get_generation:
            first, second = asyncio.run(receive_push())

        self.assertIn("status", first)
        self.assertIn("event: completed", second)
        get_generation.assert_called_once_with("image-prompt", user_id)


if __name__ == "__main__":
    unittest.main()
