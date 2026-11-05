# test_accountless

## 공용 사용

인증 없는 API 접근과 계정 경로 제거를 검사한다. LOCAL_FIELD_MIGRATION_TESTS=1이면 실제 PostgreSQL의 격리된 임시 스키마에서 신규·기존 DB 전환, 계정정보 삭제, 콘텐츠·공용 토큰·외부 파일 참조 보존과 재실행을 검사하고 모두 롤백한다.
