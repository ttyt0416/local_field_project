import unittest
from unittest.mock import patch
from uuid import uuid4

from app import uploads
from app.auth import UserResponse


class UploadsRouteTest(unittest.TestCase):
    def test_list_passes_media_filter_and_page_to_database(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with (
            patch.object(uploads, "storage_enabled", return_value=True),
            patch.object(uploads, "list_reusable_media", return_value=([], 21)) as list_assets,
        ):
            result = uploads.reusable_media("", "latest", False, "image", 2, user)

        self.assertEqual(result.items, [])
        self.assertEqual(result.page, 2)
        self.assertEqual(result.page_size, 10)
        self.assertEqual(result.total_count, 21)
        self.assertEqual(result.total_pages, 3)
        list_assets.assert_called_once_with(
            user.id,
            search="",
            sort="latest",
            include_generated=False,
            media_kind="image",
            page=2,
        )


if __name__ == "__main__":
    unittest.main()
