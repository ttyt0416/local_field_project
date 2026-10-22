# Docker Compose 실행 계약

`docker compose up -d`는 `docker-compose.production.yml`을 기본으로 사용한다. Source 변경을 image에 반영하려면 기존과 같이 `docker compose up -d --build`를 사용한다.

개발 환경은 `docker compose -f docker-compose.development.yml up -d`로 실행한다. 두 환경은 같은 project name과 named volume을 유지하므로 production database와 web log volume 이름을 변경하지 않는다.

SkinTokens는 호스트의 독립 local-field-rigging 사용자 서비스(8190 포트)로 실행한다. production/development server 모두 RIGGING_URL을 host.docker.internal:8190으로 설정하며, rigging/.runtime/token을 /run/secrets/rigging_token에 읽기 전용으로 mount한다. 먼저 rigging/README.md에 따라 worker를 시작해 token 파일을 만든다. source 변경 반영을 위한 web/server rebuild는 별도 배포 작업이다.
