import unittest
from datetime import datetime, timezone
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app import vault
from app.auth import UserResponse
from app.storage import StorageError


class VaultRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user = UserResponse(id=uuid4(), username="tester")

    def test_list_passes_search_sort_favorites_and_page_to_database(self) -> None:
        with patch.object(vault, "list_image_generations", return_value=([], 21, 17)) as list_images:
            result = vault.vault_images("portrait", "most_viewed", True, 2, self.user)

        self.assertEqual(result.items, [])
        self.assertEqual(result.page, 2)
        self.assertEqual(result.page_size, 10)
        self.assertEqual(result.total_count, 21)
        self.assertEqual(result.completed_count, 17)
        self.assertEqual(result.total_pages, 3)
        list_images.assert_called_once_with(
            self.user.id,
            search="portrait",
            sort="most_viewed",
            favorites_only=True,
            model_family=None,
            generation_mode=None,
            page=2,
        )

    def test_list_passes_exact_image_category_to_database(self) -> None:
        with patch.object(vault, "list_image_generations", return_value=([], 0, 0)) as list_images:
            vault.vault_images("", "latest", False, 1, self.user, "i2i", "illustrious")

        list_images.assert_called_once_with(
            self.user.id,
            search="",
            sort="latest",
            favorites_only=False,
            model_family="illustrious",
            generation_mode="i2i",
            page=1,
        )

    def test_list_passes_krea2_image_category_to_database(self) -> None:
        with patch.object(vault, "list_image_generations", return_value=([], 0, 0)) as list_images:
            vault.vault_images("", "latest", False, 1, self.user, "t2i", "krea2")

        list_images.assert_called_once_with(
            self.user.id,
            search="",
            sort="latest",
            favorites_only=False,
            model_family="krea2",
            generation_mode="t2i",
            page=1,
        )

    def test_krea2_image_summary_is_valid(self) -> None:
        summary = vault.VaultImageSummary(
            id=uuid4(),
            media_type="image",
            status="completed",
            prompt="portrait",
            checkpoint="krea2.safetensors",
            model_family="krea2",
            generation_mode="t2i",
            image_url=None,
            source_image_url=None,
            view_count=0,
            is_favorite=False,
            created_at=datetime.now(timezone.utc),
            completed_at=None,
            elapsed_seconds=0,
            is_edited=False,
            file_size_bytes=None,
        )

        self.assertEqual(summary.model_family, "krea2")

    def test_list_rejects_partial_image_category(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            vault.vault_images("", "latest", False, 1, self.user, "i2i")

        self.assertEqual(raised.exception.status_code, 422)

    def test_three_d_list_passes_page_to_database(self) -> None:
        with patch.object(vault, "list_three_d_generations", return_value=([], 12, 9)) as list_three_d:
            result = vault.vault_three_d("asset", "oldest", True, 2, self.user)

        self.assertEqual(result.items, [])
        self.assertEqual(result.page, 2)
        self.assertEqual(result.total_pages, 2)
        self.assertEqual(result.completed_count, 9)
        list_three_d.assert_called_once_with(
            self.user.id,
            search="asset",
            sort="oldest",
            favorites_only=True,
            page=2,
        )

    def test_video_list_passes_page_to_database(self) -> None:
        with patch.object(vault, "list_video_generations", return_value=([], 0, 0)) as list_videos:
            result = vault.vault_videos("", "latest", False, 1, self.user)

        self.assertEqual(result.items, [])
        self.assertEqual(result.page_size, 10)
        self.assertEqual(result.total_pages, 0)
        list_videos.assert_called_once_with(
            self.user.id,
            search="",
            sort="latest",
            favorites_only=False,
            page=1,
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

    def test_image_download_reads_owned_storage_as_attachment(self) -> None:
        generation_id = uuid4()
        stored = {"status": "completed", "storage_file_id": "image-file", "filename": "portrait.png"}
        with (
            patch.object(vault, "get_image_generation_by_id", return_value=stored) as get_generation,
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "storage_download_file", return_value=(b"image", "image/png")) as download,
        ):
            response = vault.download_vault_image(generation_id, self.user)

        self.assertEqual(response.body, b"image")
        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.headers["content-disposition"], "attachment; filename=\"portrait.png\"; filename*=UTF-8''portrait.png")
        get_generation.assert_called_once_with(generation_id, self.user.id)
        download.assert_called_once_with(file_id="image-file", owner_id=str(self.user.id))

    def test_video_download_reads_owned_storage_as_attachment(self) -> None:
        generation_id = uuid4()
        stored = {"status": "completed", "storage_file_id": "video-file", "filename": "scene.mp4"}
        with (
            patch.object(vault, "get_video_generation_by_id", return_value=stored) as get_generation,
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "storage_download_file", return_value=(b"video", "video/mp4")) as download,
        ):
            response = vault.download_vault_video(generation_id, self.user)

        self.assertEqual(response.body, b"video")
        self.assertEqual(response.media_type, "video/mp4")
        self.assertEqual(response.headers["content-disposition"], "attachment; filename=\"scene.mp4\"; filename*=UTF-8''scene.mp4")
        get_generation.assert_called_once_with(generation_id, self.user.id)
        download.assert_called_once_with(file_id="video-file", owner_id=str(self.user.id))

    def test_favorite_request_is_explicit(self) -> None:
        payload = vault.FavoriteRequest(is_favorite=True)
        generation_id = uuid4()
        with patch.object(vault, "update_image_favorite", return_value=True) as update:
            result = vault.update_vault_image_favorite(generation_id, payload, self.user)

        self.assertTrue(result.is_favorite)
        update.assert_called_once_with(generation_id, self.user.id, True)

    def test_bulk_delete_finishes_storage_before_database_delete(self) -> None:
        generation_ids = [uuid4(), uuid4()]
        storage_finished = Event()
        storage_calls: list[str] = []

        def delete_database(*_: object) -> int:
            if not storage_finished.is_set():
                raise AssertionError("Storage 삭제 완료 전에 DB 삭제가 시작됐습니다.")
            return len(generation_ids)

        def delete_storage(*, file_id: str, **_: object) -> None:
            storage_calls.append(file_id)
            if len(storage_calls) == 2:
                storage_finished.set()

        stored = [{"storage_file_id": "file-1"}, {"storage_file_id": "file-2"}]
        with (
            patch.object(vault, "get_image_generations_by_ids", return_value=stored),
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "has_media_asset", return_value=False),
            patch.object(vault, "has_generation_storage_reference_outside", return_value=False),
            patch.object(vault, "delete_image_generations", side_effect=delete_database) as delete_database_mock,
            patch.object(vault, "storage_delete_file", side_effect=delete_storage) as delete_storage_mock,
        ):
            result = vault.delete_vault_images(vault.BulkDeleteRequest(generation_ids=generation_ids), self.user)

        self.assertEqual(result.deleted_count, 2)
        delete_database_mock.assert_called_once_with(generation_ids, self.user.id)
        self.assertEqual(delete_storage_mock.call_count, 2)

    def test_filtered_three_d_delete_deletes_every_matching_row(self) -> None:
        generation_ids = [uuid4(), uuid4()]
        rows = [{"id": generation_id, "storage_file_id": None} for generation_id in generation_ids]
        with (
            patch.object(vault, "list_filtered_three_d_generations", return_value=rows) as list_filtered,
            patch.object(vault, "delete_three_d_generations", return_value=2) as delete_rows,
        ):
            result = vault.delete_filtered_vault_three_d("asset", False, 2, True, self.user)

        self.assertEqual(result.deleted_count, 2)
        list_filtered.assert_called_once_with(self.user.id, search="asset", favorites_only=False)
        delete_rows.assert_called_once_with(generation_ids, self.user.id)

    def test_filtered_video_delete_deletes_every_matching_row(self) -> None:
        generation_ids = [uuid4(), uuid4()]
        rows = [{"id": generation_id, "storage_file_id": None} for generation_id in generation_ids]
        with (
            patch.object(vault, "list_filtered_video_generations", return_value=rows) as list_filtered,
            patch.object(vault, "delete_video_generations", return_value=2) as delete_rows,
        ):
            result = vault.delete_filtered_vault_videos("portrait", True, 2, True, self.user)

        self.assertEqual(result.deleted_count, 2)
        list_filtered.assert_called_once_with(self.user.id, search="portrait", favorites_only=True)
        delete_rows.assert_called_once_with(generation_ids, self.user.id)

    def test_bulk_storage_failure_keeps_database_rows(self) -> None:
        generation_id = uuid4()
        stored = [{"storage_file_id": "file-1"}]
        with (
            patch.object(vault, "get_image_generations_by_ids", return_value=stored),
            patch.object(vault, "storage_enabled", return_value=True),
            patch.object(vault, "has_media_asset", return_value=False),
            patch.object(vault, "has_generation_storage_reference_outside", return_value=False),
            patch.object(vault, "storage_delete_file", side_effect=StorageError("storage failed")),
            patch.object(vault, "delete_image_generations") as delete_rows,
            self.assertRaises(HTTPException) as raised,
        ):
            vault.delete_vault_images(vault.BulkDeleteRequest(generation_ids=[generation_id]), self.user)

        self.assertEqual(raised.exception.status_code, 503)
        delete_rows.assert_not_called()

    def test_filtered_delete_rejects_changed_result_count(self) -> None:
        rows = [{"id": uuid4(), "storage_file_id": None}]
        with (
            patch.object(vault, "list_filtered_video_generations", return_value=rows),
            patch.object(vault, "delete_video_generations") as delete_rows,
            self.assertRaises(HTTPException) as raised,
        ):
            vault.delete_filtered_vault_videos("", False, 2, True, self.user)

        self.assertEqual(raised.exception.status_code, 409)
        delete_rows.assert_not_called()


if __name__ == "__main__":
    unittest.main()
