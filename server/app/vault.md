# Vault 이미지·동영상 목록 및 관리

`GET /vault/images`와 `GET /vault/videos`는 로그인한 사용자의 생성 결과를 반환한다. `search`, `sort`, `favorites_only`, `page`로 검색·정렬·즐겨찾기 필터·페이지를 처리한다. 상세 API는 사용자 소유권을 확인하고 조회수를 1 증가시킨다.

이미지 상세는 `file_size_bytes`로 파일 용량을 표시하고, 동영상 상세는 `duration_seconds`를 분·초 형식으로 표시하며 `file_size_bytes`로 파일 용량도 표시한다. 신규 생성·편집 결과는 저장 당시 실제 bytes를 기록하고, 기존 결과의 size가 없는 경우 상세 조회에서 Storage metadata를 보완 조회한다.

이미지 상세의 편집 버튼은 crop, 1.0x~3.0x 중앙 확대, 90도 단위 회전을 Canvas로 미리보고 `POST /vault/images/{generation_id}/edit`로 새 generation을 저장한다. `GET /vault/images/{generation_id}/source`는 편집용 인증 원본을 제공한다. 이미지 lightbox의 확대·축소는 표시 크기만 변경한다.

동영상 상세의 편집 버튼은 시작·종료 시간, crop 좌표, 90도 단위 회전을 입력받아 `POST /vault/videos/{generation_id}/edit`에서 FFmpeg로 새 H.264/AAC MP4를 저장한다. 모든 편집은 원본 generation과 Storage 파일을 보존한다.

`DELETE /vault/images/bulk`와 단일 삭제 API는 기존 사용자 소유권·Storage 보존 규칙을 유지한다. 생성 결과가 다른 generation의 input으로 재사용된 경우 해당 Storage 파일은 보존한다.
