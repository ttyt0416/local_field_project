# 업로드 콘텐츠 API

`GET /uploads`는 로그인한 사용자의 업로드 이미지·동영상·오디오를 소유권으로 제한해 반환하고 Storage signed URL과 파일 용량(`size`)을 함께 제공한다. `page`는 1부터 시작하고 page size는 10으로 고정한다. `search`, `sort`, `media_kind`로 검색·정렬·종류 필터를 처리하며 생성 결과 포함 여부는 `include_generated=true`로 선택한다.

`GET /uploads/{file_id}`는 업로드 콘텐츠 상세를 반환한다. 이미지와 동영상은 파일 이름, 종류, 파일 용량, Storage URL을 표시하고, 동영상은 ffprobe metadata에서 `duration_seconds`, `width`, `height`를 계산한다. 모든 조회는 현재 사용자 소유의 `media_assets` row를 먼저 확인한다.

`GET /uploads/{file_id}/source`는 이미지 편집기에서 사용할 인증된 원본 bytes를 제공한다. `POST /uploads/{file_id}/edit`는 Canvas PNG와 최종 가로·세로를 받아 업로드 이미지의 편집 결과를 새 Storage 파일과 `media_assets` row(`source_type=edited_upload`)로 저장한다. `POST /uploads/{file_id}/edit/video`는 시작·종료 시간, crop 좌표, 90도 단위 회전을 받아 FFmpeg H.264/AAC MP4와 새 `media_assets` row를 만든다. 두 편집 API 모두 원본을 수정하지 않는다.

`DELETE /uploads/{file_id}`는 소유권 확인 후 Storage 파일과 `media_assets` row를 삭제한다. Storage 삭제 실패 시 DB row를 유지해 재시도할 수 있다.
