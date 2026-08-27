# Storage 삭제 테스트

`test_vault_storage_delete.py`는 Local Field의 이미지 삭제 순서를 확인한다. Storage 파일 삭제가 먼저 성공해야 Local Field DB 레코드를 지우며, Storage 삭제 실패 시 DB 레코드를 보존한다.
