from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

from .audit import redact, request_context


logger = logging.getLogger(__name__)


def upstream_path(request: Any) -> str:
    value = request.full_url if hasattr(request, 'full_url') else str(request)
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    if ':' in host:
        host = f'[{host}]'
    if parsed.port:
        host += f':{parsed.port}'
    return str(redact(urlunsplit((parsed.scheme, host, parsed.path, '', ''))))


@contextmanager
def api_user(user_id: Any):
    token = request_context.set({**(request_context.get() or {}), 'user_id': user_id})
    try:
        yield
    finally:
        request_context.reset(token)


class ApiTimer:
    def __init__(self, method: str, path: str, *, source: str = 'upstream', user_id: Any = None,
                 metadata: dict[str, Any] | None = None):
        self.started = perf_counter()
        self.requested_at = datetime.now(timezone.utc)
        self.request_id = uuid4()
        self.metadata = dict(metadata if metadata is not None else request_context.get() or {})
        if user_id is not None:
            self.metadata['user_id'] = user_id
        self.method, self.path, self.source = method, path, source
        self.status_code = 0
        self.headers_ms: float | None = None
        self.first_byte_ms: float | None = None
        self.finished = False
        self.live = method == 'WS'

    def elapsed_ms(self) -> float:
        return round(max(0, perf_counter() - self.started) * 1000, 3)

    def headers(self, status_code: int) -> None:
        if self.finished:
            return
        if isinstance(status_code, int):
            self.status_code = status_code
        if self.headers_ms is None:
            self.headers_ms = self.elapsed_ms()
            self._record('in_progress')

    def first_byte(self) -> None:
        if self.first_byte_ms is None:
            self.first_byte_ms = self.elapsed_ms()
            if self.live:
                self._record('in_progress')

    def finish(self, outcome: str | None = None, error: BaseException | None = None) -> None:
        if self.finished:
            return
        self.finished = True
        if isinstance(error, HTTPError):
            self.status_code = error.code
            if self.headers_ms is None:
                self.headers_ms = self.elapsed_ms()
        if outcome is None:
            reason = error.reason if isinstance(error, URLError) else error
            outcome = 'timeout' if isinstance(reason, TimeoutError) else 'error' if error else 'completed'
            if error is None or isinstance(error, HTTPError):
                outcome = 'http_error' if self.status_code >= 400 else 'completed'
            if type(error).__name__ in {'CancelledError', '_ModelDownloadCancelled'}:
                outcome = 'cancelled'
            elif type(error).__name__ == 'ConnectionClosedOK':
                outcome = 'completed'
        self._record(outcome, self.elapsed_ms(), datetime.now(timezone.utc))

    def _record(self, outcome: str, duration_ms: float | None = None, finished_at: datetime | None = None) -> None:
        try:
            from .database import record_api_call
            record_api_call(method=self.method, path=self.path, status_code=self.status_code,
                            client_ip=self.metadata.get('client_ip'), user_agent=self.metadata.get('user_agent'),
                            user_id=self.metadata.get('user_id'), source=self.source, request_id=self.request_id,
                            parent_request_id=self.metadata.get('request_id'), requested_at=self.requested_at,
                            headers_ms=self.headers_ms, first_byte_ms=self.first_byte_ms,
                            duration_ms=duration_ms, finished_at=finished_at, outcome=outcome)
        except Exception:
            logger.warning('API latency record could not be prepared', exc_info=True)

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        self.finish(error=error)
        return False


class TimedResponse:
    def __init__(self, response: Any, timer: ApiTimer):
        self.response, self.timer = response, timer

    def __getattr__(self, name: str):
        return getattr(self.response, name)

    def __enter__(self):
        try:
            self.response = self.response.__enter__()
            self.timer.headers(getattr(self.response, 'status', 200))
            return self
        except BaseException as exc:
            self.timer.finish(error=exc)
            raise

    def __exit__(self, kind, error, traceback):
        try:
            return self.response.__exit__(kind, error, traceback)
        except BaseException as exc:
            self.timer.finish(error=exc)
            raise
        finally:
            self.timer.finish(error=error)

    def read(self, *args, **kwargs):
        try:
            result = self.response.read(*args, **kwargs)
            if result:
                self.timer.live = True
                self.timer.first_byte()
            amount = args[0] if args else kwargs.get('amt', kwargs.get('size'))
            if amount is None or amount < 0 or not result:
                self.timer.finish()
            return result
        except BaseException as exc:
            self.timer.finish(error=exc)
            raise

    def close(self):
        try:
            return self.response.close()
        except BaseException as exc:
            self.timer.finish(error=exc)
            raise
        finally:
            self.timer.finish()


def timed_urlopen(opener: Any, request: Any, *args, **kwargs):
    method = request.get_method() if hasattr(request, 'get_method') else 'GET'
    owner_id = None
    if hasattr(request, 'get_header'):
        try:
            owner_id = UUID(request.get_header('X-owner-id'))
        except (TypeError, ValueError, AttributeError):
            pass
    timer = ApiTimer(method, upstream_path(request), user_id=owner_id)
    try:
        response = opener(request, *args, **kwargs)
        timer.headers(getattr(response, 'status', 200))
        return TimedResponse(response, timer)
    except BaseException as exc:
        timer.finish(error=exc)
        raise


class ApiTimingMiddleware:
    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        timer = ApiTimer(scope['method'], scope['path'], source='server', metadata={
            'client_ip': scope.get('client', (None,))[0] if scope.get('client') else None,
            'user_agent': headers.get(b'user-agent', b'').decode('latin-1') or None,
        })
        state = scope.setdefault('state', {})
        state['api_request_id'] = timer.request_id
        disconnected = False
        error = None

        async def timed_receive():
            nonlocal disconnected
            message = await receive()
            if message['type'] == 'http.disconnect':
                disconnected = True
            return message

        async def timed_send(message):
            timer.metadata['user_id'] = state.get('user_id')
            if message['type'] == 'http.response.start':
                timer.live = any(key.lower() == b'content-type' and value.lower().startswith(b'text/event-stream') for key, value in message.get('headers', []))
                timer.headers(message['status'])
            elif message['type'] == 'http.response.body' and message.get('body'):
                timer.first_byte()
            await send(message)
            if message['type'] == 'http.response.body' and not message.get('more_body', False):
                timer.finish()

        try:
            await self.app(scope, timed_receive, timed_send)
        except BaseException as exc:
            error = exc
            if timer.status_code == 0:
                timer.status_code = 500
            raise
        finally:
            timer.metadata['user_id'] = state.get('user_id')
            if not timer.finished:
                if disconnected:
                    outcome = 'disconnected'
                elif error is not None:
                    outcome = None
                else:
                    outcome = 'incomplete'
                timer.finish(outcome, error)
