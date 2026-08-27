# Storage 연동

`storage.py`는 Local Field 이미지 결과를 독립 Go/Echo 파일 스토리지에 업로드하고 소유자별 만료 읽기 URL을 발급한다.

`STORAGE_URL`과 `STORAGE_API_TOKEN`이 모두 설정된 경우에만 연동을 활성화한다. 업로드 요청에는 서비스 인증 토큰과 Local Field 사용자 ID를 전달하며, 파일 자체는 Local Field DB에 저장하지 않는다. 스토리지 요청 실패는 이미지 생성 결과를 완료로 기록하지 않고 실패 상태로 처리한다.

Production 환경은 두 값을 주입해야 하며, 토큰은 소스와 문서에 기록하지 않는다.