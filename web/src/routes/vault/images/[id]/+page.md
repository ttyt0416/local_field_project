# 이미지 상세

이미지 상세 페이지는 진입할 때마다 `GET /vault/images/{generation_id}`를 호출하고 서버에서 조회수를 증가시킨다. Storage signed URL 또는 인증 이미지 프록시로 결과 이미지를 표시하며, 사용된 생성 파라미터와 프롬프트를 함께 보여준다.

상단 즐겨찾기 버튼은 `PATCH /vault/images/{generation_id}/favorite`로 상태를 저장한다. 페이지 하단의 red 이미지 삭제 버튼은 확인 모달을 연다. 확인 후 `DELETE /vault/images/{generation_id}`가 성공하면 보관함으로 이동한다. 생성 파라미터에서는 파일 경로를 표시하지 않으며 LoRA는 `이름 / strength` 형식으로 표시한다. `이 설정으로 다시 생성`을 선택하면 긍정·부정 프롬프트와 체크포인트, LoRA별 strength, CFG, Steps, 이미지 크기, seed를 `imageGenerationStore`에 저장하고 이미지 생성 화면으로 이동한다. 페이지 제목은 `이미지 상세`이며 공용 `Typography`의 축소된 `display` variant를 사용한다.
