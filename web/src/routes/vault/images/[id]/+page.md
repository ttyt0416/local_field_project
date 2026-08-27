# Vault 이미지 상세 표시

Vault 상세 응답의 이미지 URL 형식에 따라 Storage 절대 URL과 기존 Local Field 상대 URL을 구분해 `ImageMedia`에 전달한다. 상세 확대 갤러리에서도 같은 원격 소스 정책을 사용한다.

페이지 하단의 red 이미지 삭제 버튼은 확인 모달을 연다. 확인 후 `DELETE /vault/images/{generation_id}`가 성공하면 보관함으로 이동한다. 생성 파라미터에서는 파일 경로를 표시하지 않으며, 제목은 공용 `Typography`의 축소된 `display` variant를 사용한다.
