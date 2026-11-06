밀리초 단위와 monotonic 측정, 헤더/첫 청크/종료 구분, request_id에 따른 중복 종료 방지, 부모 요청·사용자 context, 느리거나 실패하는 기록 경로 격리, 응답 바이트/속성/close 보존, 리디렉션·HTTP 오류·연결 타임아웃·본문 실패, 스토리지 소유자, 백그라운드 스레드 context, ASGI SSE/500/연결 종료, DB UPSERT 인자 및 URL 자격 정보 제외를 검증한다.

## 공용 사용

계정 fixture와 소유자 인자를 제거하고 공용 데이터·API 계약으로 기존 회귀 검사를 유지한다.

## 이미지 진단 검사

중첩 TRACE와 외부 호출의 prompt_id·file_id·parent_request_id 연결, 타임아웃 시 context 복원, 브라우저 진단 context의 DB 전달과 page_path 우선순위를 검증한다.
