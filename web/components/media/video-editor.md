# 동영상 편집기

`VideoEditor`는 보관함과 업로드 콘텐츠 상세에서 native video metadata를 읽어 시작·종료 시간과 crop 좌표, 90도 단위 회전을 입력받는다. `editPath`를 받으면 업로드 전용 endpoint를 사용하고, 생략하면 보관함 endpoint를 사용한다. 편집은 FFmpeg H.264/AAC MP4로 수행하며 원본은 수정하지 않는다.
