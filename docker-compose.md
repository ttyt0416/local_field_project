# Docker Compose 실행 계약

`docker compose up -d`는 `docker-compose.production.yml`을 기본으로 사용한다. Source 변경을 image에 반영하려면 기존과 같이 `docker compose up -d --build`를 사용한다.

개발 환경은 `docker compose -f docker-compose.development.yml up -d`로 실행한다. 두 환경은 같은 project name과 named volume을 유지하므로 production database와 web log volume 이름을 변경하지 않는다.
