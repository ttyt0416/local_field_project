# 콘텐츠 다운로드

`downloadMedia`는 인증이 필요한 Local Field 상대 URL을 `apiBlob`로 가져오고, Storage signed URL 같은 외부 URL은 직접 fetch한 뒤 브라우저 다운로드를 시작한다. 호출 화면은 다운로드 중복 실행을 막기 위해 loading 상태를 관리하고 실패 시 toast를 표시한다.
