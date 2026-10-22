# Development 리깅 연결

server는 호스트 SkinTokens worker의 8190 포트를 RIGGING_URL로 사용하고 rigging/.runtime/token을 읽기 전용 secret 파일로 mount한다. 기존 개발 포트와 다른 services는 유지한다. worker 설치·시작 후 token이 존재해야 하며 실행 방법은 rigging/README.md에 있다.
