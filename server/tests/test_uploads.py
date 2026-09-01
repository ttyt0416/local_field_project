import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from fastapi import UploadFile
from starlette.datastructures import Headers

from app import uploads
from app.auth import UserResponse
from app.media_editing import VideoMetadata


class UploadsRouteTest(unittest.TestCase):
    def test_detail_returns_video_duration_and_size(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        asset = {
            "storage_file_id": "file-1",
            "filename": "clip.mp4",
            "content_type": "video/mp4",
            "media_kind": "video",
            "source_type": "generation_input",
            "created_at": datetime.now(timezone.utc),
            "size": 1234,
        }
        with (
            patch.object(uploads, "get_media_asset", return_value=asset),
            patch.object(uploads, "storage_enabled", return_value=True),
            patch.object(uploads, "storage_read_url", return_value="https://storage.test/file-1"),
            patch.object(uploads, "storage_download_file", return_value=(b"video", "video/mp4")),
            patch.object(uploads, "probe_video", return_value=VideoMetadata(1920, 1080, 65.25, 30)),
        ):
            result = uploads.upload_detail("file-1", user)

        self.assertEqual(result.size, 1234)
        self.assertEqual(result.duration_seconds, 65.25)
        self.assertEqual(result.width, 1920)
        self.assertEqual(result.height, 1080)

    def test_image_edit_creates_new_uploaded_asset(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        asset = {
            "storage_file_id": "file-1",
            "filename": "photo.jpg",
            "content_type": "image/jpeg",
            "media_kind": "image",
            "source_type": "generation_input",
            "created_at": datetime.now(timezone.utc),
            "size": 1234,
        }

        upload_file = UploadFile(
            file=BytesIO(b"png-bytes"),
            filename="edited.png",
            headers=Headers({"content-type": "image/png"}),
        )

        with (
            patch.object(uploads, "get_media_asset", return_value=asset),
            patch.object(uploads, "storage_enabled", return_value=True),
            patch.object(uploads, "storage_upload_file", return_value="new-file") as upload,
            patch.object(uploads, "create_media_asset", return_value={"storage_file_id": "new-file"}) as create,
        ):
            result = uploads.edit_uploaded_image("file-1", upload_file, 640, 480, user)

        self.assertEqual(result.generation_id, "new-file")
        upload.assert_called_once_with(content=b"png-bytes", media_type="image/png", owner_id=str(user.id))
        create.assert_called_once_with(
            user_id=user.id,
            storage_file_id="new-file",
            filename="photo-edited.png",
            content_type="image/png",
            media_kind="image",
            size=9,
            source_type="edited_upload",
        )

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
    def test_list_passes_source_filter_to_database(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with (
            patch.object(uploads, "storage_enabled", return_value=True),
            patch.object(uploads, "list_reusable_media", return_value=([], 0)) as list_assets,
        ):
            uploads.reusable_media("", "latest", True, "video", 1, user, "generated")

        list_assets.assert_called_once_with(
            user.id,
            search="",
            sort="latest",
            include_generated=True,
            media_kind="video",
            page=1,
            source_type="generated",
        )

    def test_list_passes_exact_generated_image_category_to_database(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with (
            patch.object(uploads, "storage_enabled", return_value=True),
            patch.object(uploads, "list_reusable_media", return_value=([], 0)) as list_assets,
        ):
            uploads.reusable_media("", "latest", True, "image", 1, user, "generated", "i2i", "illustrious")

        list_assets.assert_called_once_with(
            user.id,
            search="",
            sort="latest",
            include_generated=True,
            media_kind="image",
            page=1,
            source_type="generated",
            generation_mode="i2i",
            model_family="illustrious",
        )

    def test_list_passes_krea2_generated_image_category_to_database(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with (
            patch.object(uploads, "storage_enabled", return_value=True),
            patch.object(uploads, "list_reusable_media", return_value=([], 0)) as list_assets,
        ):
            uploads.reusable_media("", "latest", True, "image", 1, user, "generated", "t2i", "krea2")

        list_assets.assert_called_once_with(
            user.id,
            search="",
            sort="latest",
            include_generated=True,
            media_kind="image",
            page=1,
            source_type="generated",
            generation_mode="t2i",
            model_family="krea2",
        )

    def test_list_rejects_partial_generated_image_category(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with self.assertRaises(uploads.HTTPException) as raised:
            uploads.reusable_media("", "latest", True, "image", 1, user, "generated", "i2i")

        self.assertEqual(raised.exception.status_code, 422)

    def test_delete_removes_owned_storage_file_and_database_asset(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with (
            patch.object(uploads, "get_media_asset", return_value={"file_id": "file-1"}),
            patch.object(uploads, "storage_enabled", return_value=True),
            patch.object(uploads, "storage_delete_file") as delete_storage,
            patch.object(uploads, "delete_media_asset", return_value=True) as delete_database,
        ):
            response = uploads.delete_upload("file-1", user)

        self.assertEqual(response.status_code, 204)
        delete_storage.assert_called_once_with(file_id="file-1", owner_id=str(user.id))
        delete_database.assert_called_once_with("file-1", user.id)

    def test_delete_rejects_missing_owned_asset_before_storage_call(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        with (
            patch.object(uploads, "get_media_asset", return_value=None),
            patch.object(uploads, "storage_delete_file") as delete_storage,
        ):
            with self.assertRaises(uploads.HTTPException) as raised:
                uploads.delete_upload("other-file", user)

        self.assertEqual(raised.exception.status_code, 404)
        delete_storage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
