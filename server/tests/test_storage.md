# Storage 연동 검사

`test_storage.py`는 독립 Storage API 요청이 파일 바이트, MIME 타입, 사용자 소유자 ID, 서비스 인증 헤더를 올바르게 구성하는지 확인한다. 네트워크나 실제 토큰 없이 URL 인코딩과 응답 파싱도 검증한다.

## 공용 사용

계정 fixture와 소유자 인자를 제거하고 공용 데이터·API 계약으로 기존 회귀 검사를 유지한다.

## 읽기 URL 진단

첫 발급과 캐시 hit를 구분하고 owner_lookup_ms·file_id가 남는지 기존 요청 결과와 함께 검증한다. 감사 기록은 mock으로 대체한다.
