# Hardware metrics proxy

`GET /hardware/metrics` requires the existing bearer authentication and proxies the independent `hardware-monitor` `GET /metrics` endpoint. It validates all four percentage fields are numeric values in `[0, 100]` and returns `503` with a safe Korean error if the internal monitor is unavailable or malformed. The production Local Field server uses `http://host.docker.internal:8091`; browser code must call this authenticated proxy rather than the monitor directly.

## API 레이턴시 기록

하드웨어 모니터 API 요청을 timed_urlopen으로 측정한다.
