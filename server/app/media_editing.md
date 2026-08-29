# 동영상 편집 처리

`edit_video`는 사용자 소유 Storage에서 내려받은 영상 bytes를 임시 파일에 쓰고 `ffprobe`로 영상 크기·길이·fps를 검증한다. 지정한 구간을 frame-accurate re-encode 방식으로 자르고 crop, 90도 단위 회전을 적용한 뒤 H.264/AAC MP4로 반환한다. 임시 파일은 context manager가 정리하며 shell 문자열 조합 없이 argument list로 FFmpeg를 실행한다.
