# 이미지 진단 로그 검사

`prepare-telemetry.mjs`가 실제 image-timing·telemetry 유틸을 번들링해 `image-timing-check.html`을 만든다. fake fetch와 합성 Resource Timing으로 실제 API·개인 이미지 요청 없이 시작/종료 연결, 중복 종료 방지, 노출된 네트워크 구간, cross-origin 제한, 캐시 근거, Blob 준비 오류, native 오류 DB 기록, 미완료 지연 체크, 화면 해제, 이미 로드된 합성 이미지, 갤러리, 완료 URL 누락, 서명·이미지 바이트 제외, 기록 장애 격리를 검사한다. 네이티브 캐시 완료 검사는 테스트 내부의 1px SVG data URL을 사용한다.

준비한 HTML은 로컬 임시 서버에서 실행하며 검증 후 임시 컨테이너와 생성물을 제거한다.

추가로 실제 포커스 추적 유틸과 생성 API 측정기를 함께 실행한다. 합성 window blur/focus에서 visibility를 visible로 유지해 앱 전환 후 생성하는 경우의 시작 이력 보존, 생성 POST·SSE·결과·이미지의 page_instance_id 연결, 이미지 로드 중 포커스 이탈과 생성 전 이탈의 구별, 시작 스냅샷 불변성, 중복·요소 이벤트 제외, 12개 이력 제한, 리스너 중복 설치·해제 및 장애 격리를 확인한다. 이 검사는 계측 동작을 확인하며 실제 OS 앱 전환 시 지연 증상 재현을 대신하지 않는다.
