from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app import saved_prompts as prompts
from app.auth import UserResponse


class SavedPromptsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user = UserResponse(id=uuid4(), username="tester")
        self.connection = MagicMock()
        patcher = patch("app.saved_prompts.get_connection")
        patcher.start().return_value.__enter__.return_value = self.connection
        self.addCleanup(patcher.stop)
        now = datetime.now(timezone.utc)
        self.row = (uuid4(), "image", "Test", "new content", now, now)

    def test_create_preserves_text_and_stores_only_the_current_owner(self) -> None:
        self.connection.execute.return_value.fetchone.return_value = self.row
        payload = prompts.PromptRequest(kind="image", name=" Test ", content="first line\nsecond line")
        result = prompts.create_prompt(payload, self.user)
        self.assertEqual(self.connection.execute.call_args.args[1][1:], (self.user.id, "image", "Test", "first line\nsecond line"))
        self.assertEqual(result.id, self.row[0])

    def test_list_filters_by_owner_and_media_kind(self) -> None:
        self.connection.execute.return_value.fetchall.return_value = [self.row]
        result = prompts.list_prompts("video", self.user)
        self.assertEqual(self.connection.execute.call_args.args[1], (self.user.id, "video"))
        self.assertEqual(len(result), 1)

    def test_edit_and_delete_cannot_access_another_users_prompt(self) -> None:
        self.connection.execute.return_value.fetchone.return_value = None
        for operation in (lambda: prompts.update_prompt(self.row[0], prompts.PromptRequest(kind="image", name="Test", content="new"), self.user), lambda: prompts.delete_prompt(self.row[0], self.user)):
            with self.assertRaises(HTTPException) as raised:
                operation()
            self.assertEqual(raised.exception.status_code, 404)
            self.assertEqual(self.connection.execute.call_args.args[1][-2:], (self.row[0], self.user.id))

    def test_rejects_empty_oversized_and_non_prompt_settings(self) -> None:
        for changes in ({"name": " "}, {"content": "\n "}, {"content": "x" * 5001}, {"kind": "music"}, {"checkpoint": "model"}):
            with self.subTest(changes=list(changes)), self.assertRaises(ValidationError):
                prompts.PromptRequest(**{"kind": "image", "name": "Name", "content": "Text", **changes})


if __name__ == "__main__":
    unittest.main()
