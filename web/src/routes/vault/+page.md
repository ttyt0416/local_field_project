# Vault 이미지 목록 표시

Vault API가 반환한 Storage signed URL은 외부 이미지로 직접 로드하고, Local Field가 반환한 상대 경로는 절대 URL로 변환하지 않고 서버 이미지로 분류해 인증 Blob 로드를 사용한다. 이 구분으로 인증이 필요한 기존 생성 이미지도 표시한다.

각 카드 우측 하단의 red 삭제 아이콘은 확인 모달을 연다. 확인하면 `DELETE /vault/images/{generation_id}`를 호출하고 성공한 이미지를 목록에서 제거한다. 카드는 `cursor-pointer`이며 프롬프트와 별도 `상세 보기` 링크 없이 카드 클릭 또는 키보드 Enter/Space로 상세 페이지로 이동한다.
