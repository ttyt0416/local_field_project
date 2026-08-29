# 동영상 편집기

`VideoEditor`는 보관함 동영상 상세에서 native video metadata를 읽어 시작·종료 시간과 crop 좌표, 90도 단위 회전을 입력받는다. 편집은 `POST /vault/videos/{generation_id}/edit`에서 FFmpeg로 수행하며 원본은 수정하지 않는다.
