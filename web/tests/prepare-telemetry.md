Vite의 파일 허용 목록을 변경하지 않고 브라우저 검증 페이지를 준비한다. `node web/tests/prepare-telemetry.mjs`를 실행하면 기존 Rolldown으로 실제 telemetry 유틸과 DOM 테스트를 번들링해 임시 `web/static/audit-check.html`을 만든다. fetch는 테스트가 대체하며 실제 로그 서버로 요청하지 않는다. 로컬 임시 서버의 `/audit-check.html`을 연 뒤 결과를 확인하고 생성한 HTML을 삭제한다.

## API 레이턴시 기록

추가로 실제 API 유틸과 ky를 기존 Rolldown으로 번들링해 임시 static/api-latency-check.html을 준비한다. /audit-check.html과 /api-latency-check.html 결과를 확인한 뒤 두 생성 파일 및 개발 캐시를 삭제한다. 프레임워크 환경·서버 주소만 테스트 값으로 대체하고 API/기록 로직은 실제 소스를 사용한다.

## 이미지 지연 검사

추가로 image-timing.test.ts를 번들링해 임시 static/image-timing-check.html을 생성한다. 실제 이미지·스토리지 요청 없이 진단 lifecycle과 Resource Timing 제한을 검사하고 나머지 임시 HTML과 함께 제거한다.

세 검증 페이지 모두 Rolldown으로 실제 유틸과 의존성을 번들링한다. telemetry의 포커스 추적 의존성도 포함하며 서버 주소와 프레임워크 환경만 테스트 값으로 대체한다.
