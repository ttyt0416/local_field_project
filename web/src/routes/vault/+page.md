# Vault 이미지 목록 표시

Vault API가 반환한 이미지 URL이 Storage 절대 URL이면 직접 로드하고, 기존 Local Field 상대 프록시 URL이면 인증 Blob 로드를 사용한다. 목록에서 기존 이미지와 새 Storage 이미지를 같은 컴포넌트로 표시한다.

각 카드 우측 하단의 red 삭제 아이콘은 확인 모달을 연다. 확인하면 `DELETE /vault/images/{generation_id}`를 호출하고 성공한 이미지를 목록에서 제거한다. 카드는 `cursor-pointer`이며 프롬프트와 별도 `상세 보기` 링크 없이 카드 클릭 또는 키보드 Enter/Space로 상세 페이지로 이동한다.
