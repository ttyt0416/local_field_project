# Vault 이미지 URL

Vault 응답은 Storage 파일 ID가 있는 이미지에 대해 사용자 소유권을 확인한 뒤 Storage API에서 짧은 만료 읽기 URL을 새로 발급한다.

`DELETE /vault/images/{generation_id}`는 Storage 파일 삭제가 성공한 뒤 Local Field의 `image_generations` 레코드를 삭제한다. Storage 삭제가 실패하면 Local Field 레코드를 유지해 재시도할 수 있다. 이미 원격에서 사라진 Storage 파일은 삭제 완료로 취급한다.

Storage 파일 ID가 없는 기존 이미지는 기존 Local Field 이미지 프록시 URL을 반환한다. Storage URL 발급 실패는 이미지 목록 또는 상세 조회에서 서비스 일시 오류로 반환한다.
