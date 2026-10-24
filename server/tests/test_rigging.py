import asyncio
from datetime import datetime, timezone
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app import rigging, three_d, vault
from app.auth import UserResponse


class RiggingTest(unittest.TestCase):
    def setUp(self):
        self.user = UserResponse(id=uuid4(), username='rigging-test')
        self.row = dict(id=uuid4(), user_id=self.user.id, prompt_id=uuid4().hex, client_id='client',
                        generation_mode='rigging', status='processing', stage='rigging',
                        created_at=datetime.now(timezone.utc), elapsed_seconds=0)

    def test_rejects_another_users_vault_model(self):
        with (patch.object(rigging, 'enabled', return_value=True),
              patch.object(rigging, 'options', return_value={'ready': True}),
              patch.object(rigging, 'get_three_d_generation_by_id', return_value=None) as owned,
              patch.object(rigging, 'download_file') as download):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(rigging.create_rigging(json.dumps({'source_generation_id': str(uuid4())}), None, self.user))
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(owned.call_args.args[1], self.user.id)
        download.assert_not_called()

    def test_rejects_forged_glb_before_storage_or_worker_submission(self):
        file = UploadFile(filename='forged.glb', file=BytesIO(b'glTF' + b'\x00' * 20))
        with (patch.object(rigging, 'enabled', return_value=True),
              patch.object(rigging, 'options', return_value={'ready': True}),
              patch.object(rigging, 'upload_file') as upload,
              patch.object(rigging, 'request_worker') as submit):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(rigging.create_rigging('{}', file, self.user))
        self.assertEqual(raised.exception.status_code, 422)
        upload.assert_not_called()
        submit.assert_not_called()

    def test_terminal_rigging_result_uses_database_without_worker_or_comfy(self):
        completed = {**self.row, 'status': 'completed', 'stage': 'completed', 'storage_file_id': 'result', 'filename': 'rigged.glb'}
        with (patch.object(three_d, '_queue_position') as queue,
              patch.object(rigging, 'request_worker') as worker):
            result = three_d._history_status(completed, self.user.id)
        self.assertEqual(result.generation_mode, 'rigging')
        self.assertEqual(result.model.url, f"vault/3d/{completed['id']}/model")
        queue.assert_not_called()
        worker.assert_not_called()

    def test_stale_status_request_does_not_upload_completed_result_twice(self):
        completed = {**self.row, 'status': 'completed', 'stage': 'completed'}
        with (patch.object(rigging, 'get_three_d_generation', return_value=completed),
              patch.object(rigging, 'request_worker') as worker,
              patch.object(rigging, 'upload_file') as upload):
            result = rigging.history_status(self.row, self.user.id)
        self.assertEqual(result.status, 'completed')
        worker.assert_not_called()
        upload.assert_not_called()

    def test_cancel_connection_failure_preserves_database_job(self):
        with (patch.object(rigging, 'get_three_d_generation', return_value=self.row),
              patch.object(rigging, 'request_worker', side_effect=rigging._ComfyUIError('offline')),
              patch.object(rigging, 'update_three_d_generation_status') as update):
            with self.assertRaises(HTTPException) as raised:
                rigging.cancel_rigging(self.row, self.user.id)
        self.assertEqual(raised.exception.status_code, 503)
        update.assert_not_called()

    def test_failed_generation_keeps_worker_message_for_sse(self):
        failed = {**self.row, 'status': 'failed', 'stage': 'failed', 'error_message': 'invalid mesh'}
        with (patch.object(rigging, 'request_worker', return_value={'status': 'failed', 'stage': 'failed', 'message': 'invalid mesh'}),
              patch.object(rigging, 'get_three_d_generation', side_effect=[self.row, failed]),
              patch.object(rigging, 'update_three_d_generation_status') as update,
              patch.object(rigging, 'record_api_error')):
            result = rigging.history_status(self.row, self.user.id)
        self.assertEqual(result.message, 'invalid mesh')
        self.assertEqual(update.call_args.kwargs['error_message'], 'invalid mesh')

    def test_deleting_mesh_preserves_glb_used_as_rigging_source(self):
        row = {**self.row, 'generation_mode': 'mesh', 'status': 'completed', 'storage_file_id': 'shared-mesh'}
        with (patch.object(vault, 'get_three_d_generation_by_id', return_value=row),
              patch.object(vault, 'has_media_asset', return_value=False),
              patch.object(vault, 'has_generation_storage_reference_outside', return_value=True),
              patch.object(vault, 'storage_delete_file') as delete_file,
              patch.object(vault, 'delete_three_d_generation', return_value=True)):
            response = vault.delete_vault_three_d(row['id'], self.user)
        self.assertEqual(response.status_code, 204)
        delete_file.assert_not_called()

    def test_deleting_rigging_cleans_up_unshared_uploaded_source_and_result(self):
        row = {**self.row, 'status': 'completed', 'storage_file_id': 'result', 'source_file_id': 'uploaded-source'}
        with (patch.object(vault, 'get_three_d_generation_by_id', return_value=row),
              patch.object(vault, 'has_media_asset', return_value=False),
              patch.object(vault, 'has_generation_storage_reference_outside', return_value=False),
              patch.object(vault, 'storage_enabled', return_value=True),
              patch.object(vault, 'storage_delete_file') as delete_file,
              patch.object(vault, 'delete_three_d_generation', return_value=True)):
            vault.delete_vault_three_d(row['id'], self.user)
        self.assertEqual({call.kwargs['file_id'] for call in delete_file.call_args_list}, {'result', 'uploaded-source'})


if __name__ == '__main__':
    unittest.main()
