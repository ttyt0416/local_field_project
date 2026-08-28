import unittest
from unittest.mock import patch
from uuid import uuid4

from app import vault
from app.auth import UserResponse


class VaultRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user = UserResponse(id=uuid4(), username="tester")

    def test_list_passes_search_sort_and_favorites_to_database(self) -> None:
        with patch.object(vault, "list_image_generations", return_value=[]) as list_images:
            result = vault.vault_images("portrait", "most_viewed", True, self.user)

        self.assertEqual(result, [])
        list_images.assert_called_once_with(
            self.user.id,
            search="portrait",
            sort="most_viewed",
            favorites_only=True,
        )

    def test_detail_uses_view_count_increment(self) -> None:
        generation_id = uuid4()
        stored = {"id": generation_id}
        with (
            patch.object(vault, "increment_image_generation_view_count", return_value=stored) as increment,
            patch.object(vault, "_detail", return_value="detail") as detail,
        ):
            result = vault.vault_image_detail(generation_id, self.user)

        self.assertEqual(result, "detail")
        increment.assert_called_once_with(generation_id, self.user.id)
        detail.assert_called_once_with(stored, self.user.id)

    def test_favorite_request_is_explicit(self) -> None:
        payload = vault.FavoriteRequest(is_favorite=True)
        generation_id = uuid4()
        with patch.object(vault, "update_image_favorite", return_value=True) as update:
            result = vault.update_vault_image_favorite(generation_id, payload, self.user)

        self.assertTrue(result.is_favorite)
        update.assert_called_once_with(generation_id, self.user.id, True)


if __name__ == "__main__":
    unittest.main()
