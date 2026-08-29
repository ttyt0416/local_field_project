# 이미지 편집기

`ImageEditor`는 보관함과 업로드 콘텐츠 상세에서 인증된 원본을 Blob으로 읽고 브라우저 Canvas로 crop, 1.0x~3.0x 중앙 확대와 90도 단위 회전을 미리본다. `sourcePath`와 `editPath`를 받으면 업로드 전용 endpoint를 사용하고, 생략하면 보관함 endpoint를 사용한다. 저장 결과는 PNG와 최종 가로·세로로 전달하며 원본은 수정하지 않는다.
