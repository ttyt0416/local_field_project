# 로컬 태그·카탈로그 검증

가져오기 테스트는 ANIMADEX_DATA_DIR를 임시 디렉터리로 지정해 실제 썸네일·동기화 잠금 상태에 영향을 주지 않는다. CDN 실패 fixture는 공식 인덱스 주소를 포함한다. 썸네일 파일·delta 자체의 테스트는 test_animadex_assets.py에서 다룬다.

AnimaDex CSV 필드·빈/잘못된 스냅샷 거부·태그 보존·시리즈별 캐릭터 수 집계, 토큰의 exact manifest 호스트 제한, CSV 인증 헤더 미전송, 실패 원인 기록, 검색의 네트워크 미사용, LIKE 와일드카드 escaping과 페이지 오프셋을 검증한다. 별도 실제 PostgreSQL 임시 테이블 테스트는 반복 import·중복 처리·시리즈 필터·원자적 실패 복구를 확인하고 최종 롤백한다.

## 동작·오류 기록

가져오기·네트워크 오류 기록을 record_exception 유틸로 검증한다.
