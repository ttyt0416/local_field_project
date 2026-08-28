from __future__ import annotations

import asyncio
import logging
from typing import Any

from .comfyui import _history_generation_status
from .database import get_image_generation, get_video_generation, list_active_image_generations, list_active_video_generations
from .generation_events import generation_event_broker, generation_key
from .video import _history_status


_RECONCILE_INTERVAL_SECONDS = 2
logger = logging.getLogger(__name__)


def reconcile_active_generations() -> None:
    for generation in list_active_image_generations():
        previous_status = str(generation.get("status", "queued"))
        try:
            result = _history_generation_status(generation["prompt_id"], generation["user_id"])
            _publish_if_changed("image", generation, previous_status, result.status, result.model_dump())
        except Exception:
            logger.exception("이미지 생성 작업을 동기화하지 못했습니다: %s", generation["prompt_id"])
            _publish_terminal_if_changed("image", generation, previous_status)

    for generation in list_active_video_generations():
        previous_status = str(generation.get("status", "queued"))
        try:
            result = _history_status(generation, generation["user_id"])
            _publish_if_changed("video", generation, previous_status, result.status, result.model_dump())
        except Exception:
            logger.exception("동영상 생성 작업을 동기화하지 못했습니다: %s", generation["prompt_id"])
            _publish_terminal_if_changed("video", generation, previous_status)


def _publish_if_changed(
    kind: str,
    generation: dict[str, Any],
    previous_status: str,
    current_status: str,
    data: dict[str, Any],
) -> None:
    if current_status == previous_status:
        return
    event = current_status if current_status in {"completed", "failed"} else "status"
    generation_event_broker.publish(
        key=generation_key(kind, generation["user_id"], generation["prompt_id"]),
        event=event,
        data=data,
    )


def _publish_terminal_if_changed(kind: str, generation: dict[str, Any], previous_status: str) -> None:
    if kind == "image":
        current = get_image_generation(generation["prompt_id"], generation["user_id"])
    else:
        current = get_video_generation(generation["prompt_id"], generation["user_id"])
    if current is None or current["status"] == previous_status or current["status"] not in {"completed", "failed"}:
        return
    generation_event_broker.publish(
        key=generation_key(kind, generation["user_id"], generation["prompt_id"]),
        event=current["status"],
        data={"prompt_id": generation["prompt_id"], "status": current["status"]},
    )


async def run_generation_reconciler(stop_event: asyncio.Event) -> None:
    logger.info("generation reconciler started")
    try:
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(reconcile_active_generations)
            except Exception:
                logger.exception("생성 작업 목록을 동기화하지 못했습니다.")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_RECONCILE_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
    finally:
        logger.info("generation reconciler stopped")
