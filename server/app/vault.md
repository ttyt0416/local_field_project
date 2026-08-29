# Vault 이미지·동영상 목록 및 관리

`GET /vault/images`와 `GET /vault/videos`는 로그인한 사용자의 생성 결과를 반환한다. `search`가 있으면 프롬프트를 부분 검색하고, `sort`는 `latest`, `oldest`, `most_viewed` 중 하나로 정렬한다. `favorites_only=true`이면 즐겨찾기한 결과만 반환한다. `page`는 1부터 시작하며 고정 page size는 10이다. 응답은 `items`, `page`, `page_size`, `total_count`, `completed_count`, `total_pages`를 포함한다. `completed_count`는 기존 콘텐츠 수 표시를 위해 필터 전체에서 완료된 결과만 센다.

이미지와 동영상은 같은 보관함 경로에서 별도 탭으로 조회한다. 상세 API는 사용자 소유권을 확인하고 조회수를 1 증가시킨다. favorite PATCH는 명시적인 `is_favorite` 값을 저장해 재시도에도 결정적으로 동작한다. 이미지 상세의 편집 버튼은 crop과 90도 단위 회전을 Canvas로 미리보고 `POST /vault/images/{generation_id}/edit`로 새 generation을 저장한다. `GET /vault/images/{generation_id}/source`는 편집용 인증 원본을 제공한다. 이미지 lightbox는 100%부터 400%까지 확대·축소할 수 있다.

`DELETE /vault/images/bulk`는 최대 100개의 사용자 소유 이미지와 Storage 파일을 삭제한다. Storage 파일 삭제 작업과 Local Field DB 레코드 삭제 작업은 표준 라이브러리 스레드 풀에서 병렬로 시작하며, 각 Storage 파일 삭제에는 기존 소유자 검증을 적용한다.

단일 삭제 API는 Storage 파일 삭제가 성공한 뒤 Local Field의 레코드를 삭제한다. 단, 결과가 다른 generation의 input으로 재사용되어 `media_assets`에 기록된 경우에는 Storage 파일을 보존하고 generation row만 삭제한다. Storage 삭제가 실패하면 레코드를 유지해 재시도할 수 있다. 영상 단일 삭제도 같은 Storage 소유권 검증을 사용한다.
