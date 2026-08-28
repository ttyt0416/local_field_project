# Vault 이미지 목록 및 관리

`GET /vault/images`는 로그인한 사용자의 생성 결과를 반환한다. `search`가 있으면 저장된 긍정 프롬프트를 부분 검색하고, `sort`는 `latest`, `oldest`, `most_viewed` 중 하나로 정렬한다. `favorites_only=true`이면 즐겨찾기한 결과만 반환한다.

`GET /vault/images/{generation_id}`는 사용자 소유권을 확인한 뒤 상세 정보를 반환하고 `view_count`를 1 증가시킨다. `PATCH /vault/images/{generation_id}/favorite`는 `is_favorite` 값을 명시적으로 변경한다. 즐겨찾기 상태는 생성 결과 레코드에 저장되며 보관함의 별도 즐겨찾기 메뉴에서 필터링한다.

`DELETE /vault/images/bulk`는 최대 100개의 사용자 소유 콘텐츠를 한 번에 삭제한다. Storage 파일 삭제 작업과 Local Field DB 레코드 삭제 작업은 표준 라이브러리 스레드 풀에서 병렬로 시작하며, 각 Storage 파일 삭제에는 기존 소유자 검증을 적용한다.

프롬프트 검색은 `image_generations.prompt`에 대한 PostgreSQL `pg_trgm` GIN 인덱스를 사용한다. 단일 삭제 API는 Storage 파일 삭제가 성공한 뒤 Local Field의 레코드를 삭제한다. Storage 삭제가 실패하면 단일 레코드를 유지해 재시도할 수 있다.

Storage 파일 ID가 없는 기존 이미지는 기존 Local Field 이미지 프록시 URL을 반환한다. Storage URL 발급 실패는 이미지 목록 또는 상세 조회에서 서비스 일시 오류로 반환한다.
