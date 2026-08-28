# Application layout

애플리케이션 전역 레이아웃은 라우트 이동과 button·link·checkbox 클릭을 `web/events` 감사 API에 기록한다. checkbox는 선택 상태 변경을 구분하기 위해 `target_type=checkbox`로 기록한다.