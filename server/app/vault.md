# Vault 이미지·동영상 목록 및 관리

`GET /vault/images`와 `GET /vault/videos`는 로그인한 사용자의 생성 결과를 반환한다. `search`, `sort`, `favorites_only`, `page`로 검색·정렬·즐겨찾기 필터·페이지를 처리한다. 상세 API는 사용자 소유권을 확인하고 조회수를 1 증가시킨다.

이미지 상세는 `file_size_bytes`로 파일 용량을 표시하고, 동영상 상세는 `duration_seconds`를 분·초 형식으로 표시하며 `file_size_bytes`로 파일 용량도 표시한다. 신규 생성·편집 결과는 저장 당시 실제 bytes를 기록하고, 기존 결과의 size가 없는 경우 상세 조회에서 Storage metadata를 보완 조회한다.

이미지 상세의 편집 버튼은 crop, 1.0x~3.0x 중앙 확대, 90도 단위 회전을 Canvas로 미리보고 `POST /vault/images/{generation_id}/edit`로 새 generation을 저장한다. `GET /vault/images/{generation_id}/source`는 편집용 인증 원본을 제공한다. 이미지 lightbox의 확대·축소는 표시 크기만 변경한다.

동영상 상세의 편집 버튼은 시작·종료 시간, crop 좌표, 90도 단위 회전을 입력받아 `POST /vault/videos/{generation_id}/edit`에서 FFmpeg로 새 H.264/AAC MP4를 저장한다. 모든 편집은 원본 generation과 Storage 파일을 보존한다.

`DELETE /vault/images/bulk`와 단일 삭제 API는 기존 사용자 소유권·Storage 보존 규칙을 유지한다. `DELETE /vault/images/filtered`와 `DELETE /vault/videos/filtered`는 현재 `search`·`favorites_only` 조건에 맞는 모든 page의 row를 snapshot으로 조회한다. `confirmed=true`와 화면에서 확인한 `expected_count`가 일치해야 삭제하며, 개수가 바뀌면 `409`로 중단한다.

Bulk 삭제는 삭제 가능한 Storage 파일을 먼저 모두 지운 뒤 DB row를 삭제한다. Storage 삭제 하나라도 실패하면 DB row를 유지한다. 해당 파일이 `media_assets` 또는 snapshot 밖의 다른 image/video generation에서 참조되면 Storage 원본은 보존한다.
