# Booru 태그 검색

Danbooru/Gelbooru가 공유하는 태그 카드·검색·분류·페이지·복사·추가 UI다. 출처에 따라 기존 `/tags` 또는 로컬 `/tags/gelbooru`를 호출한다. Gelbooru는 일치순·사용순만 제공하고 Danbooru의 pgvector 정확도순을 유지한다. 선택한 태그는 부모에 전달하여 탭을 바꿔도 보존한다. 늦은 조회·unmount 응답은 request ID로 무시하고 통신 오류는 Toast로 표시한다.

검색 결과 안내에는 개수만 표시하고 출처별 로컬 태그 설명 문구는 표시하지 않는다.
