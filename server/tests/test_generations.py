from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from app.auth import UserResponse
from app import generations


class ActiveGenerationRouteTest(unittest.TestCase):
    def test_returns_only_current_users_active_image_and_video_rows(self) -> None:
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
        with (
            patch.object(generations, "list_active_image_generations", return_value=[image]) as image_list,
            patch.object(generations, "list_active_video_generations", return_value=[video]) as video_list,
        ):
            result = generations.active_generations(user)

        image_list.assert_called_once_with(user.id)
        video_list.assert_called_once_with(user.id)
        self.assertEqual([item.kind for item in result], ["image", "video"])
        self.assertEqual(result[0].status, "processing")
        self.assertEqual(result[1].mode, "i2v")


if __name__ == "__main__":
    unittest.main()
