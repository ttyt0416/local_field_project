# Development 리깅 연결

server는 호스트 SkinTokens worker의 8190 포트를 RIGGING_URL로 사용하고 rigging/.runtime/token을 읽기 전용 secret 파일로 mount한다. 기존 개발 포트와 다른 services는 유지한다. worker 설치·시작 후 token이 존재해야 하며 실행 방법은 rigging/README.md에 있다.

AnimaDex 썸네일과 delta 상태는 production과 동일한 호스트 .runtime/tag-catalogues/animadex를 /var/lib/local-field/animadex에 mount해 보존한다. ANIMADEX_DATA_DIR는 이 컨테이너 경로를 가리킨다.

다운로드용 공용 토큰 파일을 서버 환경에 주입하지 않는다. Civitai와 Hugging Face 요청은 사용자가 다운로드 관리에 저장한 개인 토큰만 사용한다.
