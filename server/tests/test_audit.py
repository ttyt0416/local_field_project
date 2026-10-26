import asyncio
from io import BytesIO
import json
from queue import Queue
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.responses import StreamingResponse

from app import audit, database, main, media_editing, model_downloads, music, three_d, uploads, vault


class AuditTest(unittest.TestCase):
    def test_suppressed_original_cause_and_provider_response_are_preserved_once(self):
        try:
            try:
                raise TimeoutError('socket timed out: upstream read')
            except TimeoutError:
                error = RuntimeError('일반화 문구')
                error.provider_response = {'usage': {'completion_tokens': 123}, 'access_token': 'private'}
                raise error from None
        except RuntimeError as error:
            with patch.object(audit, 'fire_and_forget') as enqueue:
                audit.record_exception(error, operation='download', user_id='owner')
                audit.record_exception(error)
        self.assertEqual(enqueue.call_count, 1)
        payload = enqueue.call_args.args[1]
        self.assertEqual(payload['error_type'], 'TimeoutError')
        self.assertEqual(payload['error_message'], 'socket timed out: upstream read')
        self.assertEqual([item['type'] for item in payload['error_details']['chain']], ['RuntimeError', 'TimeoutError'])
        self.assertIn('test_audit.py', payload['error_details']['chain'][1]['traceback'])
        self.assertEqual(payload['provider_response']['usage']['completion_tokens'], 123)
        self.assertEqual(payload['provider_response']['access_token'], '[REDACTED]')

    def test_http_error_body_is_read_only_in_background_and_stream_close_failure_isolated(self):
        stream = BytesIO(b'{"error":"upstream original","token":"private"}')
        error = HTTPError('https://example.test/?token=private', 403, 'Forbidden', {}, stream)
        with patch.object(audit, 'fire_and_forget') as enqueue:
            audit.record_exception(error)
        self.assertEqual(stream.tell(), 0)
        callback, payload, streams = enqueue.call_args.args
        with patch.object(database, '_write_api_error') as write:
            callback(payload, streams)
        self.assertTrue(stream.closed)
        self.assertIn('upstream original', write.call_args.kwargs['error_details']['http_responses'][0]['body'])
        self.assertNotIn('private', json.dumps(write.call_args.kwargs))

    def test_errors_are_not_truncated_to_1000_characters(self):
        message = 'original ' + 'x' * 4000
        with patch.object(database, '_record') as record:
            database.record_api_error(method='GET', path='/api', status_code=500, error_type='ValueError', error_message=message, client_ip=None, user_agent=None)
        self.assertEqual(record.call_args.args[1][4], message)

    def test_validation_error_does_not_save_password_input(self):
        error = RequestValidationError([{'loc': ('body', 'password'), 'msg': 'String too short', 'type': 'string_too_short', 'input': 'private'}])
        with patch.object(audit, 'fire_and_forget') as enqueue:
            audit.record_exception(error)
        self.assertNotIn('private', json.dumps(enqueue.call_args.args[1]))
        self.assertIn('String too short', enqueue.call_args.args[1]['error_message'])

    def test_handled_http_exception_retains_original_detail(self):
        with patch.object(audit, 'fire_and_forget') as enqueue:
            audit.record_exception(HTTPException(503, 'actual service unavailable detail'), status_code=503)
        self.assertEqual(enqueue.call_args.args[1]['error_message'], 'actual service unavailable detail')

    def test_queue_never_waits_for_slow_or_broken_database(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        def slow():
            started.set()
            release.wait(3)
            raise OSError('database offline')
        channel = 'test-' + str(uuid4())
        audit.fire_and_forget(slow, channel=channel)
        self.assertTrue(started.wait(1))
        audit.fire_and_forget(finished.set, channel=channel)
        self.assertFalse(finished.is_set())
        release.set()
        self.assertTrue(finished.wait(1))

    def test_full_queue_drops_record_without_raising(self):
        queue = Queue(maxsize=1)
        queue.put_nowait(None)
        with patch.dict(audit._queues, {'full-test': queue}), self.assertLogs(audit.logger, level='WARNING'):
            audit.fire_and_forget(lambda: None, channel='full-test')
        self.assertEqual(queue.qsize(), 1)

    def test_web_event_is_queued_with_complete_identity(self):
        owner, visitor, session, event = (uuid4() for _ in range(4))
        with patch.object(database, 'fire_and_forget') as enqueue:
            database.record_web_event(event_type='click', page_path='/models?x=' + 'y' * 6000, from_path='/files', target_type='button', target_id='button:nth-of-type(1)', target_label='다운로드', target_href=None, client_ip='127.0.0.1', user_agent='test', user_id=owner, visitor_id=visitor, session_id=session, event_id=event, target_path='body > button', target_context={'dialog_label': '폴더 선택'})
        parameters = enqueue.call_args.args[1]
        self.assertEqual(parameters[9:11], (owner, event))
        self.assertEqual(parameters[12:15], (visitor, session, 'body > button'))
        self.assertGreater(len(parameters[1]), 6000)
        self.assertEqual(enqueue.call_args.kwargs['channel'], 'web')

    def test_remote_history_keeps_raw_exception_and_entire_history(self):
        payload = {'status_str': 'error', 'messages': [['execution_error', {'exception_type': 'CUDAOutOfMemoryError', 'exception_message': 'CUDA original', 'traceback': ['original frame']}]]}
        with patch.object(database, 'record_api_error') as record:
            audit.record_remote_error(payload, operation='music.history')
        self.assertEqual(record.call_args.kwargs['error_type'], 'CUDAOutOfMemoryError')
        self.assertEqual(record.call_args.kwargs['error_message'], 'CUDA original')
        self.assertEqual(record.call_args.kwargs['error_details']['remote_error'], payload)

    def test_error_response_body_capture_does_not_change_stream(self):
        async def original():
            yield b'{"detail":'
            yield b'"raw upstream"}'
        async def run():
            response = StreamingResponse(original(), status_code=502)
            audit.audit_error_response(response, method='GET', path='/api', status_code=502, client_ip=None, user_agent=None)
            return b''.join([chunk async for chunk in response.body_iterator])
        with patch.object(database, 'record_api_error') as record:
            body = asyncio.run(run())
        self.assertEqual(body, b'{"detail":"raw upstream"}')
        self.assertEqual(record.call_args.kwargs['error_message'], body.decode())

    def test_stream_failure_after_headers_is_audited_and_still_raises(self):
        async def original():
            yield 'first'
            raise OSError('stream original failure')
        async def run():
            return [chunk async for chunk in audit.audit_stream(original(), operation='music.events', user_id='owner')]
        with patch.object(audit, 'record_exception') as record, self.assertRaisesRegex(OSError, 'stream original failure'):
            asyncio.run(run())
        self.assertEqual(str(record.call_args.args[0]), 'stream original failure')
        self.assertEqual(record.call_args.kwargs['user_id'], 'owner')

    def test_music_and_3d_options_log_recovered_errors(self):
        for module, function in [(music, music.music_options), (three_d, three_d.three_d_options)]:
            with self.subTest(module=module.__name__), patch.object(module, '_readiness', side_effect=module._ComfyUIError('raw readiness')), patch.object(module, 'record_exception') as record:
                function()
                self.assertEqual(str(record.call_args.args[0]), 'raw readiness')

    def test_subprocess_keeps_stderr_and_return_code(self):
        import subprocess
        completed = subprocess.CompletedProcess(['ffmpeg'], 7, 'stdout', 'original codec error')
        with patch.object(media_editing.subprocess, 'run', return_value=completed), self.assertRaises(media_editing.MediaEditError) as raised:
            media_editing._run(['ffmpeg'], 1, '일반 문구')
        self.assertEqual(raised.exception.__cause__.stderr, 'original codec error')
        self.assertEqual(raised.exception.__cause__.returncode, 7)

    def test_download_worker_persists_original_failure(self):
        stop = asyncio.Event()
        job = {'id': uuid4(), 'user_id': uuid4(), 'filename': 'model.safetensors', 'provider': 'civitai'}
        error = TimeoutError('The read operation timed out')
        def process(_):
            stop.set()
            raise error
        with patch.object(model_downloads, 'reset_model_downloads'), patch.object(model_downloads, 'claim_model_download', return_value=job), patch.object(model_downloads, '_process_model_download', side_effect=process), patch.object(model_downloads, 'fail_model_download') as fail, patch.object(model_downloads, 'record_exception') as record:
            asyncio.run(model_downloads.run_model_download_worker(stop))
        fail.assert_called_once_with(job['id'], 'The read operation timed out')
        record.assert_called_once()
        self.assertIsInstance(record.call_args.args[0], TimeoutError)
        self.assertEqual(str(record.call_args.args[0]), str(error))

    def test_telemetry_auth_verifies_user_without_database_dependency(self):
        from app.auth import _create_access_token
        from starlette.requests import Request
        user_id = uuid4()
        token = _create_access_token(user_id, 'audit-test')
        request = Request({'type': 'http', 'headers': [(b'authorization', f'Bearer {token}'.encode())]})
        with patch.object(database, 'get_connection', side_effect=AssertionError('must not connect')):
            self.assertEqual(main.telemetry_user(request), user_id)

    def test_upload_cleanup_failure_is_audited_without_raising(self):
        from app.auth import UserResponse
        user = UserResponse(id=uuid4(), username='audit-test')
        with patch.object(uploads, 'storage_delete_file', side_effect=uploads.StorageError('raw cleanup')), patch.object(uploads, 'record_exception') as record:
            uploads._remove_storage_file('file-id', user)
        self.assertEqual(str(record.call_args.args[0]), 'raw cleanup')
        self.assertEqual(record.call_args.kwargs['user_id'], user.id)

    def test_vault_size_lookup_failure_is_audited_without_hiding_item(self):
        user_id = uuid4()
        with patch.object(vault, 'storage_enabled', return_value=True), patch.object(vault, 'storage_file_size', side_effect=vault.StorageError('raw metadata failure')), patch.object(vault, 'record_exception') as record:
            self.assertIsNone(vault._generation_file_size({'storage_file_id': 'file-id'}, user_id, True))
        self.assertEqual(str(record.call_args.args[0]), 'raw metadata failure')

    def test_fastapi_boundary_preserves_original_errors_and_validation_details(self):
        from fastapi import FastAPI
        from pydantic import BaseModel
        from starlette.exceptions import HTTPException as StarletteHTTPException
        application = FastAPI()
        application.add_exception_handler(StarletteHTTPException, main.audit_handled_exception)
        application.add_exception_handler(RequestValidationError, main.audit_validation_exception)
        application.middleware('http')(main.audit_api_requests)

        @application.get('/wrapped')
        def wrapped():
            try:
                raise TimeoutError('original upstream timeout')
            except TimeoutError as exc:
                raise HTTPException(503, '사용자 안내 문구') from exc

        class Payload(BaseModel):
            count: int

        @application.post('/validate')
        def validate(payload: Payload):
            return payload

        async def request(path, body=b'', method='GET'):
            received = asyncio.Queue()
            received.put_nowait({'type': 'http.request', 'body': body, 'more_body': False})
            messages = []
            async def send(message):
                messages.append(message)
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method, 'path': path,
                     'raw_path': path.encode(), 'query_string': b'', 'root_path': '', 'scheme': 'http',
                     'server': ('test', 80), 'client': ('127.0.0.1', 1234), 'headers': [(b'content-type', b'application/json')]}
            await asyncio.wait_for(application(scope, received.get, send), 2)
            return messages

        with patch.object(audit, 'fire_and_forget') as enqueue, patch.object(main, 'record_api_call'):
            messages = asyncio.run(request('/wrapped'))
            self.assertEqual(messages[0]['status'], 503)
            self.assertEqual(json.loads(messages[1]['body'])['detail'], '사용자 안내 문구')
            self.assertEqual(enqueue.call_args.args[1]['error_message'], 'original upstream timeout')
            self.assertEqual(enqueue.call_args.args[1]['path'], '/wrapped')
            messages = asyncio.run(request('/validate', b'{"count":"invalid"}', 'POST'))
            self.assertEqual(messages[0]['status'], 422)
            self.assertIn('int_parsing', enqueue.call_args.args[1]['error_message'])
            self.assertIsNone(audit.request_context.get())
