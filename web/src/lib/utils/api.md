# API DELETE 요청

`apiDelete`는 Local Field의 204 No Content 삭제 응답을 JSON 파싱 없이 처리하고, 기존 공용 HTTP 오류 메시지 변환을 재사용한다. 인증 토큰은 기존 API client hook이 자동으로 전달한다.

HTTP 오류의 Ky HTTPError.data에 문자열 detail이 있으면 해당 사용자용 서버 메시지를 우선 표시한다. Ky가 이미 소비한 response body를 다시 파싱하지 않는다. 폴더 이름 중복·진행 중인 다운로드·삭제 확인 이후 내용 변경을 구분할 수 있다. detail이 없거나 문자열이 아니면 기존 상태 코드별 메시지로 대체한다.

## 동작·오류 기록

apiJson/apiForm/apiBlob/apiDelete/streamSse는 사용자 안내 문구로 바꾸기 전에 reportApiError를 호출하고 원래 Error를 cause로 보존한다. 기록 완료는 기다리지 않는다.
