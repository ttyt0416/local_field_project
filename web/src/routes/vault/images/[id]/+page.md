# Vault 이미지 상세 표시

Vault 상세 응답의 Storage signed URL은 외부 이미지로 직접 로드하고, Local Field 상대 URL은 인증 Blob 로드로 처리한다. 상대 URL을 프론트에서 절대 URL로 바꾸지 않아 보호된 기존 이미지도 인증 헤더와 함께 불러온다.

페이지 하단의 red 이미지 삭제 버튼은 확인 모달을 연다. 확인 후 `DELETE /vault/images/{generation_id}`가 성공하면 보관함으로 이동한다. 생성 파라미터에서는 파일 경로를 표시하지 않으며, 제목은 공용 `Typography`의 축소된 `display` variant를 사용한다.
