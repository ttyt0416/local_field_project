실제 apiJson/apiForm/apiBlob/apiDelete/streamSse/downloadMedia와 telemetry 유틸을 브라우저에서 검증한다. 준비 스크립트가 프로젝트의 기존 Rolldown으로 테스트를 번들링하며 환경 값만 테스트용으로 대체한다. 네트워크는 fake fetch로 제어하고 다운로드 링크 클릭도 대체하므로 실제 API 호출이나 파일 다운로드를 만들지 않는다. 성공·HTTP 오류·잘못된 JSON·연결 오류·취소·타임아웃·사용자 응답 훅 보존·SSE 최초 청크와 종료·스트림 실패·외부 다운로드·기록 지연/실패 격리를 확인한다.

실제 브라우저에서 32개 검사를 수행한다.
