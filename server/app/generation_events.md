# Generation events

`generation_events.py`는 서버 worker와 generation SSE endpoint 사이의 in-process event broker다.

- SSE 연결 시 endpoint가 사용자 소유 generation을 DB에서 한 번 조회해 현재 상태를 먼저 보낸다.
- 이후 worker가 DB commit을 마친 뒤 상태 변경을 publish하고, SSE가 해당 generation에만 push한다.
- SSE가 끊겼다가 재연결되면 새 연결의 DB snapshot이 누락된 상태를 보완한다.
- 사용자 ID와 generation 종류·prompt ID를 event key에 포함해 다른 사용자의 작업이 전달되지 않는다.

## 공용 사용

Local Field 계정 인증과 사용자별 소유자 인자를 제거하고 콘텐츠·작업을 공용으로 처리한다. 외부 서비스의 API 토큰과 기존 오류 기록은 유지한다.
