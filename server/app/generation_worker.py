from __future__ import annotations

import asyncio
import logging

from .comfyui import _history_generation_status
from .database import list_active_image_generations, list_active_video_generations
from .video import _history_status


_RECONCILE_INTERVAL_SECONDS = 2
logger = logging.getLogger(__name__)


def reconcile_active_generations() -> None:
    for generation in list_active_image_generations():
        try:
            _history_generation_status(generation["prompt_id"], generation["user_id"])
        except Exception:
            logger.exception("이미지 생성 작업을 동기화하지 못했습니다: %s", generation["prompt_id"])

    for generation in list_active_video_generations():
        try:
            _history_status(generation, generation["user_id"])
        except Exception:
            logger.exception("동영상 생성 작업을 동기화하지 못했습니다: %s", generation["prompt_id"])


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
