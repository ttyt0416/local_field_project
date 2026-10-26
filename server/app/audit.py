from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
from queue import Queue
import re
from threading import Lock, Thread
import traceback
from typing import Any, Callable
from urllib.error import HTTPError


logger = logging.getLogger(__name__)
request_context: ContextVar[dict[str, Any] | None] = ContextVar("audit_request_context", default=None)
_queues: dict[str, Queue] = {}
_queue_lock = Lock()
_SECRET_KEYS = re.compile(r"^(?:password|authorization|api.?key|token|secret|signature|credential|access_token|refresh_token|id_token|x-export-token|x-amz-signature|x-amz-credential)$|(?:_password|_secret|_api_key)$", re.I)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): "[REDACTED]" if _SECRET_KEYS.search(str(key)) else redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)([?&](?:[^=&\s]*(?:token|signature|credential|api_key|secret)[^=&\s]*)=)[^&\s'\"]+", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)((?:['\"]?(?:password|authorization|api_key|access_token|refresh_token|token|secret|signature|credential|x-export-token)['\"]?)\s*[:=]\s*)(['\"])(.*?)\2", r"\1'[REDACTED]'", value)
    return value.replace("\x00", "\\u0000") if isinstance(value, str) else value


def _consume(queue: Queue) -> None:
    while True:
        callback, args, kwargs = queue.get()
        try:
            callback(*args, **kwargs)
        except Exception:
            logger.exception("Audit write failed")
        finally:
            queue.task_done()


def fire_and_forget(callback: Callable[..., Any], *args: Any, channel: str = "api", **kwargs: Any) -> None:
    try:
        with _queue_lock:
            queue = _queues.get(channel)
            if queue is None:
                queue = Queue(maxsize=4096)
                _queues[channel] = queue
                Thread(target=_consume, args=(queue,), name=f"audit-{channel}", daemon=True).start()
        queue.put_nowait((callback, args, kwargs))
    except Exception:
        logger.warning("Audit record could not be queued", exc_info=True)


def exception_message(error: BaseException) -> str:
    seen: set[int] = set()
    current = error
    while id(current) not in seen:
        seen.add(id(current))
        nested = current.__cause__ or current.__context__
        if nested is None:
            break
        current = nested
    return str(redact(_message(current)))


def _message(error: BaseException) -> str:
    if callable(getattr(error, "errors", None)):
        try:
            errors = [{key: value for key, value in item.items() if key not in {"input", "ctx", "url"}} for item in error.errors()]
            return json.dumps(errors, ensure_ascii=False, default=str)
        except Exception:
            pass
    detail = getattr(error, "detail", None)
    return str(error) if detail is None else detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, default=str)


def _snapshot(error: BaseException) -> tuple[dict[str, Any], list[Any]]:
    chain = []
    streams = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        item = {
            "type": type(current).__name__,
            "message": _message(current),
            "traceback": "".join(traceback.format_list(traceback.extract_tb(current.__traceback__))),
        }
        for key in ("errno", "filename", "filename2", "returncode", "stderr", "stdout", "code", "reason", "doc"):
            value = getattr(current, key, None)
            if value is not None:
                item[key] = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
        if isinstance(current, HTTPError) and getattr(current, "fp", None) is not None and not getattr(current.fp, "closed", False):
            streams.append(current.fp)
        chain.append(item)
        current = current.__cause__ or current.__context__
    return redact({"chain": chain}), streams


def _persist_exception(payload: dict[str, Any], streams: list[Any]) -> None:
    from .database import _write_api_error

    responses = []
    for stream in streams:
        try:
            body = stream.read(2 * 1024 * 1024 + 1)
            responses.append({"body": redact(body[:2 * 1024 * 1024].decode("utf-8", errors="replace")), "truncated": len(body) > 2 * 1024 * 1024})
        except Exception as exc:
            responses.append({"read_error": str(redact(str(exc)))})
        finally:
            try:
                stream.close()
            except Exception:
                logger.warning("Audit HTTP stream could not be closed", exc_info=True)
    if responses:
        payload["error_details"]["http_responses"] = responses
    _write_api_error(**payload)


def record_exception(error: BaseException, *, operation: str | None = None, user_id: Any = None,
                     status_code: int = 500, context: dict[str, Any] | None = None,
                     provider_response: dict[str, Any] | None = None,
                     request_metadata: dict[str, Any] | None = None) -> None:
    try:
        current: BaseException | None = error
        chain: list[BaseException] = []
        while current is not None and all(current is not item for item in chain):
            if getattr(current, "_audit_recorded", False):
                return
            chain.append(current)
            current = current.__cause__ or current.__context__
        details, streams = _snapshot(error)
        for item in chain:
            item._audit_recorded = True
        if provider_response is None:
            provider_response = next((getattr(item, "provider_response", None) for item in chain
                                      if getattr(item, "provider_response", None) is not None), None)
        existing = request_metadata or request_context.get() or {}
        payload = {
            "method": existing.get("method", "WORKER"),
            "path": existing.get("path", operation or "background"),
            "status_code": status_code,
            "error_type": details["chain"][-1]["type"],
            "error_message": exception_message(error),
            "client_ip": existing.get("client_ip"),
            "user_agent": existing.get("user_agent"),
            "user_id": user_id if user_id is not None else existing.get("user_id"),
            "provider_response": redact(provider_response or getattr(error, "provider_response", None)),
            "error_details": {**details, "operation": operation, "context": redact(context or {}), "occurred_at": datetime.now(timezone.utc).isoformat()},
        }
        fire_and_forget(_persist_exception, payload, streams, channel="error")
    except Exception:
        logger.exception("Exception audit could not be prepared")


def record_remote_error(payload: dict[str, Any], *, operation: str, user_id: Any = None) -> None:
    try:
        from .database import record_api_error

        source = payload
        for entry in payload.get("messages", []):
            if isinstance(entry, (list, tuple)) and len(entry) > 1 and entry[0] == "execution_error" and isinstance(entry[1], dict):
                source = entry[1]
        existing = request_context.get() or {}
        record_api_error(method=existing.get("method", "WORKER"), path=existing.get("path", operation), status_code=500,
                         error_type=str(source.get("exception_type") or "RemoteExecutionError"),
                         error_message=str(source.get("exception_message") or source.get("message") or json.dumps(payload, ensure_ascii=False, default=str)),
                         client_ip=existing.get("client_ip"), user_agent=existing.get("user_agent"), user_id=user_id if user_id is not None else existing.get("user_id"),
                         error_details={"remote_error": redact(payload), "operation": operation})
    except Exception:
        logger.exception("Remote error audit could not be prepared")


def audit_error_response(response: Any, **metadata: Any) -> None:
    def save(body: bytes, truncated: bool) -> None:
        from .database import record_api_error
        record_api_error(**metadata, error_type="HTTPResponseError",
                         error_message=body.decode("utf-8", errors="replace"),
                         error_details={"response_body_truncated": truncated})

    body = getattr(response, "body", None)
    if isinstance(body, bytes):
        save(body[:2 * 1024 * 1024], len(body) > 2 * 1024 * 1024)
        return
    iterator = response.body_iterator

    async def capture():
        chunks = bytearray()
        truncated = False
        try:
            async for chunk in iterator:
                try:
                    raw = chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk)
                    remaining = max(0, 2 * 1024 * 1024 - len(chunks))
                    chunks.extend(raw[:remaining])
                    truncated = truncated or len(raw) > remaining
                except Exception:
                    logger.warning("Error response audit capture failed", exc_info=True)
                yield chunk
        finally:
            save(bytes(chunks), truncated)

    response.body_iterator = capture()


def audit_stream(iterator: Any, *, operation: str, user_id: Any = None, context: dict[str, Any] | None = None):
    metadata = dict(request_context.get() or {})

    async def stream():
        try:
            async for chunk in iterator:
                yield chunk
        except Exception as exc:
            record_exception(exc, operation=operation, user_id=user_id, context=context, request_metadata=metadata)
            raise

    return stream()
