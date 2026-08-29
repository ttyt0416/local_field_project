# Backend startup lifecycle

FastAPI lifespan은 database schema를 초기화한 뒤 generation reconciler와 Civitai model download worker를 시작한다. 두 worker 모두 stop event를 받아 graceful shutdown하며, Civitai download job은 브라우저 연결과 무관하게 DB 상태를 source of truth로 사용한다.

모델 파일은 backend container에 mount된 ComfyUI models directory 아래에 저장한다. 실제 Civitai token은 환경 변수로만 주입하고 애플리케이션 응답이나 log에 노출하지 않는다.
