import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app import vault
from app.auth import UserResponse
from app.storage import StorageError


class VaultDeleteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.generation_id = uuid4()
        self.user = UserResponse(id=uuid4(), username="tester")

    def test_storage_is_deleted_before_local_record(self) -> None:
        events: list[str] = []
        with (
            patch.object(
                vault,
                "get_image_generation_by_id",
                return_value={"storage_file_id": "file-id"},
            ),
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "has_media_asset", return_value=False),
            patch.object(vault, "storage_delete_file", side_effect=lambda **_: events.append("storage")),
            patch.object(vault, "delete_image_generation", side_effect=lambda *_: events.append("database") or True),
        ):
            response = vault.delete_vault_image(self.generation_id, self.user)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(events, ["storage", "database"])

    def test_storage_failure_keeps_local_record(self) -> None:
        with (
            patch.object(
                vault,
                "get_image_generation_by_id",
                return_value={"storage_file_id": "file-id"},
            ),
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "has_media_asset", return_value=False),
            patch.object(vault, "storage_delete_file", side_effect=StorageError("storage unavailable")),
            patch.object(vault, "delete_image_generation") as delete_database,
        ):
            with self.assertRaises(HTTPException) as raised:
                vault.delete_vault_image(self.generation_id, self.user)

        self.assertEqual(raised.exception.status_code, 503)
        delete_database.assert_not_called()

    def test_used_generation_keeps_storage_when_generation_is_deleted(self) -> None:
        with (
            patch.object(vault, "get_image_generation_by_id", return_value={"storage_file_id": "file-id"}),
            patch.object(vault, "has_media_asset", return_value=True),
            patch.object(vault, "storage_delete_file") as delete_storage,
            patch.object(vault, "delete_image_generation", return_value=True) as delete_database,
        ):
            response = vault.delete_vault_image(self.generation_id, self.user)

        self.assertEqual(response.status_code, 204)
        delete_storage.assert_not_called()
        delete_database.assert_called_once_with(self.generation_id, self.user.id)


if __name__ == "__main__":
    unittest.main()
