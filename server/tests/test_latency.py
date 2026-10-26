import asyncio
from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request
from uuid import uuid4

from app import database, latency
from app.audit import request_context


class Response(BytesIO):
    status = 200
    headers = {'Content-Length': '4'}


class LatencyTest(unittest.TestCase):
    def test_milliseconds_phases_and_idempotent_completion(self):
        with patch.object(latency, 'perf_counter', side_effect=[10, 10.02, 10.04, 10.25]), patch.object(database, 'record_api_call') as record:
            timer = latency.ApiTimer('GET', '/test')
            timer.live = True
            timer.headers(200)
            timer.first_byte()
            timer.finish()
            timer.finish()
        calls = [item.kwargs for item in record.call_args_list]
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]['headers_ms'], 20)
        self.assertIsNone(calls[0]['duration_ms'])
        self.assertEqual(calls[1]['first_byte_ms'], 40)
        self.assertEqual(calls[2]['duration_ms'], 250)
        self.assertEqual(calls[2]['outcome'], 'completed')
        self.assertIsNotNone(calls[2]['finished_at'])
        self.assertEqual(len({item['request_id'] for item in calls}), 1)

    def test_parent_request_and_user_are_captured_before_background_write(self):
        user, parent = uuid4(), uuid4()
        token = request_context.set({'user_id': user, 'request_id': parent, 'path': '/feature'})
        try:
            with patch.object(database, 'record_api_call') as record:
                timer = latency.ApiTimer('POST', 'https://provider.test/api')
                request_context.set(None)
                timer.finish()
            self.assertEqual(record.call_args.kwargs['user_id'], user)
            self.assertEqual(record.call_args.kwargs['parent_request_id'], parent)
            self.assertEqual(record.call_args.kwargs['source'], 'upstream')
        finally:
            request_context.reset(token)

    def test_recording_failure_cannot_change_success(self):
        with patch.object(database, 'record_api_call', side_effect=OSError('audit offline')), self.assertLogs(latency.logger, level='WARNING'):
            with latency.ApiTimer('GET', '/test') as timer:
                timer.headers(200)

    def test_upstream_preserves_response_stream_and_times_until_eof(self):
        response = Response(b'abcd')
        with patch.object(database, 'record_api_call') as record:
            with latency.timed_urlopen(lambda request, **kwargs: response, Request('https://provider.test/file?token=private'), timeout=5) as stream:
                self.assertEqual(stream.status, 200)
                self.assertEqual(stream.read(2), b'ab')
                self.assertIsNone(record.call_args.kwargs['duration_ms'])
                self.assertEqual(stream.read(2), b'cd')
                self.assertEqual(stream.read(2), b'')
                self.assertIsNotNone(record.call_args.kwargs['duration_ms'])
        self.assertTrue(response.closed)
        self.assertEqual(record.call_args.kwargs['path'], 'https://provider.test/file')
        self.assertEqual(record.call_args.kwargs['outcome'], 'completed')

    def test_redirect_and_http_error_status_keep_original_exception(self):
        for code, outcome in [(302, 'completed'), (403, 'http_error'), (503, 'http_error')]:
            error = HTTPError('https://provider.test', code, 'original', {}, None)
            def open_error(*args, **kwargs): raise error
            with self.subTest(code=code), patch.object(database, 'record_api_call') as record, self.assertRaises(HTTPError) as raised:
                latency.timed_urlopen(open_error, Request('https://provider.test'))
            self.assertIs(raised.exception, error)
            self.assertEqual(record.call_args.kwargs['status_code'], code)
            self.assertEqual(record.call_args.kwargs['outcome'], outcome)

    def test_connect_and_body_read_failures_are_timed_and_reraised(self):
        error = URLError(TimeoutError('socket timeout'))
        def fail(*args, **kwargs): raise error
        with patch.object(database, 'record_api_call') as record, self.assertRaises(URLError):
            latency.timed_urlopen(fail, Request('https://provider.test'))
        self.assertEqual(record.call_args.kwargs['outcome'], 'timeout')
        class BrokenResponse(Response):
            def read(self, *args, **kwargs): raise OSError('body connection reset')
        with patch.object(database, 'record_api_call') as record, self.assertRaisesRegex(OSError, 'body connection reset'):
            with latency.timed_urlopen(lambda *args: BrokenResponse(b''), Request('https://provider.test')) as response:
                response.read()
        self.assertEqual(record.call_args.kwargs['outcome'], 'error')

    def test_storage_owner_is_retained_without_thread_request_context(self):
        user_id = uuid4()
        request = Request('https://storage.test/file', headers={'X-Owner-ID': str(user_id)})
        with patch.object(database, 'record_api_call') as record:
            with latency.timed_urlopen(lambda *args: Response(b''), request) as response:
                response.read()
        self.assertEqual(record.call_args.kwargs['user_id'], user_id)

    def test_user_context_reaches_worker_and_is_restored(self):
        user_id = uuid4()
        async def run():
            with latency.api_user(user_id):
                result = await asyncio.to_thread(lambda: latency.ApiTimer('GET', '/worker').metadata['user_id'])
            return result
        self.assertEqual(asyncio.run(run()), user_id)
        self.assertIsNone(request_context.get())

    def test_asgi_headers_first_body_and_full_stream_duration(self):
        now = [1.0]
        user_id = uuid4()
        async def app(scope, receive, send):
            scope['state']['user_id'] = user_id
            now[0] = 1.05
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/event-stream')]})
            now[0] = 1.08
            await send({'type': 'http.response.body', 'body': b'event: status\n\n', 'more_body': True})
            now[0] = 1.4
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})
        messages = []
        async def send(message): messages.append(message)
        with patch.object(latency, 'perf_counter', side_effect=lambda: now[0]), patch.object(database, 'record_api_call') as record:
            asyncio.run(latency.ApiTimingMiddleware(app)({'type': 'http', 'method': 'GET', 'path': '/events'}, None, send))
        calls = [item.kwargs for item in record.call_args_list]
        self.assertEqual(calls[0]['headers_ms'], 50)
        self.assertEqual(calls[1]['first_byte_ms'], 80)
        self.assertEqual(calls[-1]['duration_ms'], 400)
        self.assertEqual(calls[-1]['source'], 'server')
        self.assertEqual(calls[-1]['user_id'], user_id)
        self.assertEqual([item['type'] for item in messages], ['http.response.start', 'http.response.body', 'http.response.body'])

    def test_asgi_error_and_client_disconnect_finish_metrics(self):
        async def fail(scope, receive, send): raise OSError('original app failure')
        async def send(message): pass
        with patch.object(database, 'record_api_call') as record, self.assertRaisesRegex(OSError, 'original app failure'):
            asyncio.run(latency.ApiTimingMiddleware(fail)({'type': 'http', 'method': 'POST', 'path': '/error'}, None, send))
        self.assertEqual(record.call_args.kwargs['status_code'], 500)
        self.assertEqual(record.call_args.kwargs['outcome'], 'error')
        async def disconnected(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await receive()
        async def receive(): return {'type': 'http.disconnect'}
        with patch.object(database, 'record_api_call') as record:
            asyncio.run(latency.ApiTimingMiddleware(disconnected)({'type': 'http', 'method': 'GET', 'path': '/events'}, receive, send))
        self.assertEqual(record.call_args.kwargs['outcome'], 'disconnected')
        self.assertIsNotNone(record.call_args.kwargs['duration_ms'])

    def test_database_parameters_use_one_upserted_request_and_original_request_time(self):
        from datetime import datetime, timezone
        request_id = uuid4()
        requested_at = datetime.now(timezone.utc)
        with patch.object(database, '_record') as record:
            database.record_api_call(method='GET', path='/api', status_code=200, client_ip=None, user_agent=None,
                                     request_id=request_id, requested_at=requested_at, duration_ms=123.456, outcome='completed')
        statement, parameters = record.call_args.args
        self.assertIn('ON CONFLICT (request_id)', statement)
        self.assertEqual(parameters[6], request_id)
        self.assertEqual(parameters[9], requested_at)
        self.assertEqual(parameters[12], 123.456)

    def test_upstream_url_does_not_store_credentials_or_query(self):
        self.assertEqual(latency.upstream_path('https://user:private@example.test:443/path?token=private#fragment'), 'https://example.test:443/path')

    def test_explicit_response_close_failure_is_timed_and_preserved(self):
        class BrokenClose:
            status = 200
            def close(self): raise OSError('original close error')
        with patch.object(database, 'record_api_call') as record, self.assertRaisesRegex(OSError, 'original close error'):
            latency.timed_urlopen(lambda *args: BrokenClose(), Request('https://provider.test')).close()
        self.assertEqual(record.call_args.kwargs['outcome'], 'error')

    def test_disconnect_cancellation_preserves_observed_disconnect_outcome(self):
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await receive()
            raise asyncio.CancelledError()
        async def receive(): return {'type': 'http.disconnect'}
        async def send(message): pass
        with patch.object(database, 'record_api_call') as record, self.assertRaises(asyncio.CancelledError):
            asyncio.run(latency.ApiTimingMiddleware(app)({'type': 'http', 'method': 'GET', 'path': '/events'}, receive, send))
        self.assertEqual(record.call_args.kwargs['outcome'], 'disconnected')
