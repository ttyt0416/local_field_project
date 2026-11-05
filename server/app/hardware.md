# Hardware metrics proxy

`GET /hardware/metrics` works without login and proxies the independent `hardware-monitor` `GET /metrics` endpoint. It validates all four percentage fields are numeric values in `[0, 100]` and returns `503` with a safe Korean error if the internal monitor is unavailable or malformed. The production Local Field server uses `http://host.docker.internal:8091`; browser code must call this Local Field proxy rather than the monitor directly.

## API 레이턴시 기록

하드웨어 모니터 API 요청을 timed_urlopen으로 측정한다.

## 공용 사용

Local Field 계정 인증과 사용자별 소유자 인자를 제거하고 콘텐츠·작업을 공용으로 처리한다. 외부 서비스의 API 토큰과 기존 오류 기록은 유지한다.
