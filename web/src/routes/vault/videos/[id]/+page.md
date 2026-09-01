# 동영상 콘텐츠 상세

동영상 보관함의 설명 링크는 `/vault/videos/{id}`로 이동하고 상세 API 진입 시 조회수를 증가시킨다. 상세 페이지는 동영상, 생성 방식, FPS, 상태, 생성 시각, 분·초 형식의 재생 시간, 파일 용량, 소요 시간, 조회수와 favorite 상태를 표시한다. 영상 자체는 재생을 유지하며 우측 하단에 `GET /vault/videos/{generation_id}/download` authenticated attachment response를 쓰는 다운로드와 favorite 아이콘 버튼을 제공한다.

`동영상 편집`은 시작·종료 시간, crop 좌표, 90도 단위 회전을 입력받아 `POST /vault/videos/{generation_id}/edit`에서 FFmpeg로 새 MP4를 저장한다. 원본은 보존하고 편집 결과 상세에는 `편집 결과` badge를 표시한다. 기존 결과에 저장된 용량이 없으면 상세 조회에서 Storage metadata를 보완한다.
