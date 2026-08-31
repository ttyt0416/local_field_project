from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from .comfyui import _history_generation_status, generation_progress, record_comfy_progress, stream_comfy_progress
from .database import (
    get_image_generation,
    get_three_d_generation,
    get_video_generation,
    list_active_image_generations,
    list_active_three_d_generations,
    list_active_video_generations,
)
from .generation_events import generation_event_broker, generation_key
from .three_d import _history_status as _three_d_history_status
from .video import _history_status


_RECONCILE_INTERVAL_SECONDS = 2
logger = logging.getLogger(__name__)
_last_published_signatures: dict[str, tuple[Any, ...]] = {}


def reconcile_active_generations() -> None:
    for generation in list_active_image_generations():
        previous_status = str(generation.get("status", "queued"))
        try:
            result = _history_generation_status(generation["prompt_id"], generation["user_id"])
            _publish_if_changed("image", generation, previous_status, result.status, result.model_dump(mode="json"))
        except Exception:
            logger.exception("이미지 생성 작업을 동기화하지 못했습니다: %s", generation["prompt_id"])
            _publish_terminal_if_changed("image", generation, previous_status)

    for generation in list_active_video_generations():
        previous_status = str(generation.get("status", "queued"))
        try:
            result = _history_status(generation, generation["user_id"])
            _publish_if_changed("video", generation, previous_status, result.status, result.model_dump(mode="json"))
        except Exception:
            logger.exception("동영상 생성 작업을 동기화하지 못했습니다: %s", generation["prompt_id"])
            _publish_terminal_if_changed("video", generation, previous_status)

    for generation in list_active_three_d_generations():
        previous_status = str(generation.get("status", "queued"))
        try:
            result = _three_d_history_status(generation, generation["user_id"])
            _publish_if_changed("3d", generation, previous_status, result.status, result.model_dump(mode="json"))
        except Exception:
            logger.exception("3D 생성 작업을 동기화하지 못했습니다: %s", generation["prompt_id"])
            _publish_terminal_if_changed("3d", generation, previous_status)


def _publish_if_changed(
    kind: str,
    generation: dict[str, Any],
    previous_status: str,
    current_status: str,
    data: dict[str, Any],
) -> None:
    key = generation_key(kind, generation["user_id"], generation["prompt_id"])
    data = {"prompt_id": generation["prompt_id"], "status": current_status, "progress": 0.0, "queue_position": None, **data}
    created_at = generation.get("created_at")
    if created_at is not None:
        data["created_at"] = created_at.isoformat() if hasattr(created_at, "isoformat") else created_at
    signature = (
        current_status,
        data.get("stage"),
        data.get("progress"),
        data.get("queue_position"),
        data.get("elapsed_seconds"),
    )
    if _last_published_signatures.get(key) == signature:
        return
    _last_published_signatures[key] = signature
    event = current_status if current_status in {"completed", "failed", "cancelled"} else "status"
    generation_event_broker.publish(
        key=key,
        event=event,
        data=data,
    )


def _publish_terminal_if_changed(kind: str, generation: dict[str, Any], previous_status: str) -> None:
    if kind == "image":
        current = get_image_generation(generation["prompt_id"], generation["user_id"])
    elif kind == "video":
        current = get_video_generation(generation["prompt_id"], generation["user_id"])
    else:
        current = get_three_d_generation(generation["prompt_id"], generation["user_id"])
    if current is None or current["status"] == previous_status or current["status"] not in {"completed", "failed", "cancelled"}:
        return
    key = generation_key(kind, generation["user_id"], generation["prompt_id"])
    progress = 100.0 if current["status"] == "completed" else generation_progress(generation["prompt_id"], generation["user_id"])["progress"]
    created_at = current.get("created_at")
    data = {
        "prompt_id": generation["prompt_id"],
        "status": current["status"],
        "progress": progress,
        "queue_position": None,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "elapsed_seconds": float(current.get("elapsed_seconds") or 0),
    }
    signature = (current["status"], data["progress"], data["queue_position"], data["elapsed_seconds"])
    if _last_published_signatures.get(key) == signature:
        return
    _last_published_signatures[key] = signature
    generation_event_broker.publish(
        key=key,
        event=current["status"],
        data=data,
    )


def _active_generations() -> list[tuple[str, dict[str, Any]]]:
    return [
        *(("image", generation) for generation in list_active_image_generations()),
        *(("video", generation) for generation in list_active_video_generations()),
        *(("3d", generation) for generation in list_active_three_d_generations()),
    ]


async def _watch_progress(kind: str, generation: dict[str, Any], stop_event: asyncio.Event) -> None:
    prompt_id = generation["prompt_id"]
    user_id = generation["user_id"]
    while not stop_event.is_set():
        try:
            async for event_name, data in stream_comfy_progress(generation["client_id"], stop_event):
                if record_comfy_progress(prompt_id, user_id, event_name, data):
                    continue
        except Exception:
            logger.debug("%s 생성 progress WebSocket 연결을 재시도합니다: %s", kind, prompt_id, exc_info=True)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass


async def run_generation_reconciler(stop_event: asyncio.Event) -> None:
    logger.info("generation reconciler started")
    listeners: dict[str, asyncio.Task[None]] = {}
    try:
        while not stop_event.is_set():
            try:
                active = await asyncio.to_thread(_active_generations)
                active_keys = set()
                for kind, generation in active:
                    key = generation_key(kind, generation["user_id"], generation["prompt_id"])
                    active_keys.add(key)
                    task = listeners.get(key)
                    if task is None or task.done():
                        listeners[key] = asyncio.create_task(_watch_progress(kind, generation, stop_event))
                for key in set(listeners) - active_keys:
                    listeners.pop(key).cancel()
                await asyncio.to_thread(reconcile_active_generations)
            except Exception:
                logger.exception("생성 작업 목록을 동기화하지 못했습니다.")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_RECONCILE_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
    finally:
        for task in listeners.values():
            task.cancel()
        if listeners:
            await asyncio.gather(*listeners.values(), return_exceptions=True)
        logger.info("generation reconciler stopped")
