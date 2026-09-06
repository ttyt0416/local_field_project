# Vault API 테스트

검색어·정렬·즐겨찾기 필터가 DB 함수로 전달되는지, 상세 조회가 조회수 증가 함수를 사용하는지, 동영상 상세가 persisted steps와 PDD state를 반환하는지, 즐겨찾기 변경이 명시적인 boolean을 전달하는지 검증한다. bulk 삭제 테스트는 Storage 파일 삭제가 DB 레코드 삭제보다 먼저 완료되는지 확인한다.
