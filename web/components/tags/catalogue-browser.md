# 로컬 캐릭터·아티스트·시리즈

공유 CatalogueBrowser는 로컬 카탈로그 API만 사용하며 이름·태그 검색, 정렬, 페이지, 트리거 복사·추가와 시리즈별 캐릭터 탐색을 제공한다. 서버에 초기 데이터가 없으면 준비 실패와 원인을 표시하고 외부 검색·이미지 요청으로 대체하지 않는다. 페이지/필터 변경의 늦은 응답은 무시한다.

세 종류 카드의 thumb_url은 공유 ImageMedia의 server 소스로 불러온다. 인증 Blob 요청, 확대 갤러리, 로딩과 object URL 정리를 재사용한다. 로컬 파일이 없는 항목에는 등록된 썸네일이 없다는 placeholder를 표시하며 이미지 통신 오류는 ImageMedia의 선택적 onerror callback으로 Toast에 전달한다.
