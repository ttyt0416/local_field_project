# Backend startup lifecycle

FastAPI lifespan은 database schema를 초기화한 뒤 image·video·3D generation reconciler와 Civitai·Hugging Face model download worker를 시작한다. worker는 stop event를 받아 graceful shutdown하며, generation과 Civitai download job은 브라우저 연결과 무관하게 DB 상태를 source of truth로 사용한다.

모델 파일은 backend container에 mount된 ComfyUI models directory 아래에 저장한다. 다운로드 token은 사용자별 암호화 저장소에서 읽고, 없으면 환경 변수 기본값을 사용한다. 애플리케이션 응답이나 log에는 원문을 노출하지 않는다. `/models/tokens`와 `/saved-prompts`는 기존 HTTP 감사 미들웨어를 통해 호출·오류를 기록한다.

HTTP audit middleware는 route가 request state에 둔 failed provider response를 `api_error_logs.provider_response`로 함께 기록한다. handled 4xx/5xx도 generic status만 남기지 않고 provider response가 있으면 해당 JSONB를 같은 error row에 보관한다.

리깅 router `/generation/3d/rigging`는 3D의 동적 prompt_id 경로보다 먼저 등록한다. HTTP audit는 기존 middleware를 사용하고, 리깅 서비스 내부 호출과 worker 오류도 audit/error DB에 기록한다.

`/tags/gelbooru`와 `/tags/catalogue`는 인증된 로컬 카탈로그 검색 router다. 시작 시 스키마만 준비하고 외부 데이터 다운로드나 동기화를 자동 실행하지 않는다.

## 동작·오류 기록

HTTP/검증 예외의 원인 체인을 보존하고 직접 반환한 오류 Response는 실제 본문을 기록한다. /web/events와 /web/errors는 DB 저장 완료를 기다리지 않고 204를 반환한다. 사용자 식별은 JWT 서명·만료를 검증하며 사용자 DB 조회를 기다리지 않는다. 웹 이벤트는 요소 경로·모달·시각·사용자·방문자·세션과 라우트 정보를 받는다.

## API 레이턴시 기록

전역 ASGI ApiTimingMiddleware로 모든 HTTP 응답과 스트림 종료 시간을 기록한다. 기존 오류 미들웨어는 원문 보존을 담당하며 중복 호출 기록을 제거했다. /web/api-timings는 브라우저 시간·상태·페이지·세션을 검증해 source=browser로 비대기 저장한다.
