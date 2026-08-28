# Vault 이미지 목록 표시

Vault API는 Storage signed URL이 있는 이미지에는 외부 이미지 URL을, Local Field가 반환한 상대 경로에는 인증 Blob 로드를 사용한다. 목록은 최신순·오래된순·많이 본 순으로 정렬할 수 있고, SearchBar는 저장된 긍정 프롬프트를 서버에서 검색한다.

보관함의 화면 순서는 제목, SearchBar와 정렬 선택, 생성된 이미지 수, 이미지 목록이다. 제목 영역에는 별도 컨테이너·아이콘·설명·로그아웃 버튼을 두지 않는다. 생성된 이미지 수는 완료된 생성 결과만 센다.

각 카드의 즐겨찾기 버튼은 `PATCH /vault/images/{generation_id}/favorite`로 상태를 저장하고, 삭제 아이콘은 확인 모달 뒤 `DELETE /vault/images/{generation_id}`를 호출한다. 카드는 상세 링크를 제공하며, 상세 API에 진입할 때마다 조회수가 증가한다.
