# Application layout

애플리케이션 전역 레이아웃은 라우트 이동과 button·link·checkbox 클릭을 `web/events` 감사 API에 기록한다. checkbox는 선택 상태 변경을 구분하기 위해 `target_type=checkbox`로 기록한다.

## 동작·오류 기록

전 페이지에 installInteractionAudit을 한 번 설치·해제한다. afterNavigate는 최초 진입·라우트 전환·뒤로/앞으로 이동의 이전/다음 경로, query/hash, navigation_type과 route ID를 기록한다.
