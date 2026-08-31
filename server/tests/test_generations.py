from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from app.auth import UserResponse
from app import generations


class ActiveGenerationRouteTest(unittest.TestCase):
    def test_returns_only_current_users_active_generation_rows(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        created_at = datetime.now(timezone.utc)
        image = {
            "id": uuid4(),
            "prompt_id": "image-prompt",
            "client_id": "image-client",
            "status": "processing",
            "created_at": created_at,
        }
        video = {
            "id": uuid4(),
            "prompt_id": "video-prompt",
            "client_id": "video-client",
            "mode": "i2v",
            "status": "queued",
            "created_at": created_at,
        }
        three_d = {
            "id": uuid4(),
            "prompt_id": "3d-prompt",
            "client_id": "3d-client",
            "preset": "standard",
            "seed": 123,
            "stage": "shape",
            "status": "processing",
            "created_at": created_at,
        }
        with (
            patch.object(generations, "list_active_image_generations", return_value=[image]) as image_list,
            patch.object(generations, "list_active_video_generations", return_value=[video]) as video_list,
            patch.object(generations, "list_active_three_d_generations", return_value=[three_d]) as three_d_list,
        ):
            result = generations.active_generations(user)

        image_list.assert_called_once_with(user.id)
        video_list.assert_called_once_with(user.id)
        three_d_list.assert_called_once_with(user.id)
        self.assertEqual([item.kind for item in result], ["image", "video", "3d"])
        self.assertEqual(result[0].status, "processing")
        self.assertEqual(result[1].mode, "i2v")
        self.assertEqual(result[2].stage, "shape")
        self.assertEqual(result[2].preset, "standard")
        self.assertEqual(result[2].seed, 123)


if __name__ == "__main__":
    unittest.main()
