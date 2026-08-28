from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator


def generation_key(kind: str, user_id: object, prompt_id: str) -> str:
    return f"{kind}:{user_id}:{prompt_id}"


class GenerationEventBroker:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    @asynccontextmanager
    async def subscribe(self, key: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(key, set()).add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers.get(key)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(key, None)

    def publish(self, *, key: str, event: str, data: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        message = {"event": event, "data": data}
        try:
            self._loop.call_soon_threadsafe(self._publish_now, key, message)
        except RuntimeError:
            return

    def _publish_now(self, key: str, message: dict[str, Any]) -> None:
        for queue in self._subscribers.get(key, set()):
            queue.put_nowait(message)


generation_event_broker = GenerationEventBroker()
