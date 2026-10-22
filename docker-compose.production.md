# Production 리깅 연결

기존 production services와 포트는 유지한다. server는 호스트 SkinTokens worker의 8190 포트를 RIGGING_URL로 사용하고 rigging/.runtime/token을 읽기 전용 secret 파일로 mount한다. worker 설치·시작 후 token이 존재해야 한다. 변경한 web/server의 image 반영은 별도 배포 절차다. 자세한 실행 방법은 rigging/README.md와 docker-compose.md에 있다.
