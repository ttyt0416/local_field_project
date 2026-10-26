# 콘텐츠 다운로드

`downloadMedia`는 인증이 필요한 Local Field 상대 URL을 `apiBlob`로 가져오고, Storage signed URL 같은 외부 URL은 직접 fetch한 뒤 브라우저 다운로드를 시작한다. 호출 화면은 다운로드 중복 실행을 막기 위해 loading 상태를 관리하고 실패 시 toast를 표시한다.

## 동작·오류 기록

외부 다운로드 HTTP 상태·본문·원래 예외를 공통 유틸에 전달한다. 내부 다운로드는 apiBlob 기록을 재사용하고 사용자 안내 예외에도 cause를 유지한다.

## API 레이턴시 기록

외부 다운로드는 시작·헤더·Blob 읽기 완료 및 실패까지 시간을 기록한다. 내부 API 다운로드는 apiBlob의 측정을 재사용한다.
