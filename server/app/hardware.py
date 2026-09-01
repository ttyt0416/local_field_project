from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import UserResponse, current_user
from .configs.constants import settings

router = APIRouter(prefix="/hardware", tags=["hardware"])
_TIMEOUT_SECONDS = 4
_METRIC_KEYS = ("cpu_percent", "gpu_percent", "ram_percent", "disk_percent")


class HardwareMetricsResponse(BaseModel):
    cpu_percent: float
    gpu_percent: float
    ram_percent: float
    disk_percent: float


class HardwareMonitorError(RuntimeError):
    pass


@router.get("/metrics", response_model=HardwareMetricsResponse)
def hardware_metrics(_: UserResponse = Depends(current_user)) -> HardwareMetricsResponse:
    try:
        return HardwareMetricsResponse(**fetch_hardware_metrics())
    except HardwareMonitorError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="하드웨어 모니터에 연결할 수 없습니다.") from exc


def fetch_hardware_metrics() -> dict[str, float]:
    url = f"{settings.hardware_monitor_url.rstrip('/')}/metrics"
    try:
        with urlopen(UrlRequest(url, headers={"Accept": "application/json"}), timeout=_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    except (UrlHTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HardwareMonitorError("hardware monitor request failed") from exc
    if not isinstance(payload, dict):
        raise HardwareMonitorError("invalid hardware monitor response")
    try:
        return {key: _percentage(payload, key) for key in _METRIC_KEYS}
    except (TypeError, ValueError) as exc:
        raise HardwareMonitorError("invalid hardware monitor response") from exc


def _percentage(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ValueError(key)
    return float(value)
