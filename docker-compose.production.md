# Production 리깅 연결

AnimaDex 썸네일은 server의 ANIMADEX_DATA_DIR=/var/lib/local-field/animadex에 저장하며 호스트 .runtime/tag-catalogues/animadex를 bind mount한다. 컨테이너 재생성·이미지 rebuild 후에도 썸네일과 delta 상태를 보존한다. 가져오기는 docker compose exec -T server python -B -m app.animadex로 실행한다.

기존 production services와 포트는 유지한다. server는 호스트 SkinTokens worker의 8190 포트를 RIGGING_URL로 사용하고 rigging/.runtime/token을 읽기 전용 secret 파일로 mount한다. worker 설치·시작 후 token이 존재해야 한다. 변경한 web/server의 image 반영은 별도 배포 절차다. 자세한 실행 방법은 rigging/README.md와 docker-compose.md에 있다.
