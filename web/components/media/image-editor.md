# 이미지 편집기

`ImageEditor`는 보관함 이미지 상세에서 인증된 원본을 Blob으로 읽고 브라우저 Canvas로 crop, 1.0x~3.0x 중앙 확대와 90도 단위 회전을 미리보기한다. 저장할 때 결과 PNG와 최종 가로·세로를 `POST /vault/images/{generation_id}/edit`로 보내며 원본은 수정하지 않는다.
