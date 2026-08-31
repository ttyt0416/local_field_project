# Vault 콘텐츠 목록 표시

Vault API는 Storage signed URL이 있는 이미지에는 외부 이미지 URL을, Local Field가 반환한 상대 경로에는 인증 Blob 로드를 사용한다. 목록은 최신순·오래된순·많이 본 순으로 정렬할 수 있고, SearchBar는 저장된 생성 결과를 서버에서 검색한다. 이미지·동영상·3D 목록은 필터 적용 후 page size 10으로 표시하며, `page`와 전체 `total_pages`를 API에서 받아 ChevronLeft·ChevronRight 버튼으로 이동한다.

보관함의 화면 순서는 제목, SearchBar와 정렬 선택, 콘텐츠 수, 이미지 목록이다. 초기 로딩 중에도 Layout·제목·검색·정렬을 유지하고 이미지 목록 영역만 `LoadingSpinner`로 표시한다. 제목 영역에는 별도 컨테이너·아이콘·설명·로그아웃 버튼을 두지 않는다. 보관함의 수와 빈 상태 문구는 `생성된 콘텐츠`, 즐겨찾기 화면에서는 `즐겨찾기 콘텐츠`를 사용하며 완료된 생성 결과만 센다. 이미지 카드 타입은 `T2I|I2I · Anima|Illustrious`로 표시한다.

각 이미지 카드는 동영상 카드와 같은 설명 영역 구조를 사용한다. 설명 상단에는 타입·상태와 생성 시각, 프롬프트를 표시하고 하단에는 좌측에 체크포인트(모델명), `소요 n분 n초`, `조회 n`을 각각 한 줄씩 표시한다. 같은 하단 row 우측에는 가로 1열로 다운로드·favorite·삭제 아이콘 버튼을 배치한다. favorite는 filled primary 버튼, 삭제는 destructive 버튼을 사용하며 이미지 위에는 좌측 상단 콘텐츠 선택 checkbox만 둔다. 카드의 이미지와 설명 링크는 `/vault/images/{generation_id}` 상세로 이동한다. 영상 카드도 영상 영역과 설명 링크를 유지하고 설명 하단 row에 FPS·소요·조회 및 다운로드·favorite·삭제 버튼을 제공한다.

3D 탭은 `GET /vault/3d`의 page 응답을 사용한다. 목록 카드는 무거운 모델 파일 대신 서버의 소스 이미지 thumbnail을 공용 이미지 컴포넌트로 표시한다. 카드에는 프리셋·Seed·소요 시간·파일 용량·조회수를 표시하며 다운로드·favorite·삭제 패턴을 그대로 재사용한다. 상세 링크는 `/vault/3d/{generation_id}`로 이동하고 필터 전체 삭제는 `DELETE /vault/3d/filtered`를 사용한다.
