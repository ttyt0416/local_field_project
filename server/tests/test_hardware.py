import json
import unittest
import uuid
from dataclasses import replace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from app import hardware
from app.auth import UserResponse, current_user
from app.configs.constants import settings


class _Response:
    def __init__(self, payload: object):
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class HardwareMonitorTest(unittest.TestCase):
    def test_fetches_all_valid_percentages_from_configured_monitor(self) -> None:
        payload = {"cpu_percent": 10, "gpu_percent": 20.5, "ram_percent": 30, "disk_percent": 40}
        with (
            patch("app.hardware.settings", replace(settings, hardware_monitor_url="http://monitor.internal:8091/")),
            patch("app.hardware.urlopen", return_value=_Response(payload)) as open_url,
        ):
            result = hardware.fetch_hardware_metrics()

        self.assertEqual(result, {key: float(value) for key, value in payload.items()})
        self.assertEqual(open_url.call_args.args[0].full_url, "http://monitor.internal:8091/metrics")

    def test_rejects_missing_or_invalid_percentages(self) -> None:
        with patch("app.hardware.urlopen", return_value=_Response({"cpu_percent": 101})):
            with self.assertRaises(hardware.HardwareMonitorError):
                hardware.fetch_hardware_metrics()

    def test_metrics_route_requires_authentication(self) -> None:
        request = Request({"type": "http", "headers": []})

        with self.assertRaises(HTTPException) as raised:
            current_user(request, None)

        self.assertEqual(raised.exception.status_code, 401)

    def test_metrics_route_returns_proxy_payload_for_authenticated_user(self) -> None:
        payload = {"cpu_percent": 10.0, "gpu_percent": 20.0, "ram_percent": 30.0, "disk_percent": 40.0}

        with patch("app.hardware.fetch_hardware_metrics", return_value=payload):
            response = hardware.hardware_metrics(UserResponse(id=uuid.uuid4(), username="monitor"))

        self.assertEqual(response.model_dump(), payload)


if __name__ == "__main__":
    unittest.main()
