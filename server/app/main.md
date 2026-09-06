# Backend startup lifecycle

FastAPI lifespan은 database schema를 초기화한 뒤 image·video·3D generation reconciler와 Civitai model download worker를 시작한다. worker는 stop event를 받아 graceful shutdown하며, generation과 Civitai download job은 브라우저 연결과 무관하게 DB 상태를 source of truth로 사용한다.

모델 파일은 backend container에 mount된 ComfyUI models directory 아래에 저장한다. 실제 Civitai token은 환경 변수로만 주입하고 애플리케이션 응답이나 log에 노출하지 않는다.

HTTP audit middleware는 route가 request state에 둔 failed provider response를 `api_error_logs.provider_response`로 함께 기록한다. handled 4xx/5xx도 generic status만 남기지 않고 provider response가 있으면 해당 JSONB를 같은 error row에 보관한다.
