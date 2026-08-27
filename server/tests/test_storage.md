# Storage 연동 검사

`test_storage.py`는 독립 Storage API 요청이 파일 바이트, MIME 타입, 사용자 소유자 ID, 서비스 인증 헤더를 올바르게 구성하는지 확인한다. 네트워크나 실제 토큰 없이 URL 인코딩과 응답 파싱도 검증한다.
