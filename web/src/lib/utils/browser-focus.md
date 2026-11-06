# 브라우저 포커스 이력

루트 마운트 시 한 번 설치해 이미지 생성 전의 앱 전환도 관찰한다. window의 blur/focus와 document의 visibilitychange를 별도로 기록하므로 탭이 계속 visible인 상태의 포커스 이탈도 측정한다. DOM 입력 요소의 포커스 이동은 앱 전환으로 세지 않는다. 다른 앱 이름이나 창 내용은 수집하지 않으며 blur만으로 앱 전환 여부를 확정하지 않는다.

`browserFocusContext()`는 문서별 `page_instance_id`, 관찰 시작 시각, 최근 이탈·복귀 UTC 시각, 복귀 후 경과시간(`since_last_focus_ms`), 최근 이탈 시간(`last_unfocused_ms`), 누적 이탈 시간(`unfocused_total_ms`), 전환 횟수와 최근 12개 전환을 복사해 반환한다. 경과시간은 performance.now를 사용한다. 초기부터 비활성인 경우 관찰 시작 이후 시간만 알 수 있으므로 실제 blur 시각은 null이다. `tracked_focus`는 수신한 window 이벤트 기준이며 `document_has_focus`는 측정 순간의 DOM 상태다.

SPA 라우트 이동 중에는 이력을 유지하고 전체 새로고침 시 새 page_instance_id를 만든다. 설치한 사용자 수를 세어 중복 리스너를 피하고, 마지막 해제 때 리스너와 메모리를 정리한다. 설치되지 않았거나 측정할 수 없으면 tracking_active=false로 반환한다. 전환 callback의 실패는 다른 callback이나 UI 동작으로 전파하지 않는다. 타이머, 레이아웃 측정, 이미지 요청, 재시도·취소·포커스 조작은 수행하지 않는다.
