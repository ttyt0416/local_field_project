# 동영상 편집 처리

`edit_video`는 사용자 소유 Storage에서 내려받은 영상 bytes를 임시 파일에 쓰고 `ffprobe`로 영상 크기·길이·fps를 검증한다. 지정한 구간을 frame-accurate re-encode 방식으로 자르고 crop, 90도 단위 회전을 적용한 뒤 H.264/AAC MP4로 반환한다. 임시 파일은 context manager가 정리하며 shell 문자열 조합 없이 argument list로 FFmpeg를 실행한다.

`extract_last_video_frame`는 generated segment video bytes에서 probe한 마지막 frame을 PNG로 추출한다. `concat_video_segments`는 sequence의 ordered MP4 bytes를 concat demuxer로 H.264/AAC MP4 하나로 re-encode한다. 두 helper 모두 500MB segment input cap, bounded ffprobe/ffmpeg timeout, non-empty output validation을 공유하며 only server-internal generation artifacts에 사용한다.
