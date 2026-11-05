# Storage 삭제 테스트

`test_vault_storage_delete.py`는 Local Field의 이미지 삭제 순서를 확인한다. Storage 파일 삭제가 먼저 성공해야 Local Field DB 레코드를 지우며, Storage 삭제 실패 시 DB 레코드를 보존한다.

## 공용 사용

계정 fixture와 소유자 인자를 제거하고 공용 데이터·API 계약으로 기존 회귀 검사를 유지한다.
