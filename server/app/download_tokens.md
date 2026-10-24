# 다운로드 API 토큰

`/models/tokens`는 인증된 사용자 자신의 Civitai/Hugging Face 토큰 등록 상태를 반환하고 PUT/DELETE로 저장·삭제한다. 토큰 원문·암호문은 API 응답에 반환하지 않는다. ASCII 토큰만 허용하며 요청 본문과 인증 헤더는 기존 감사 로그의 수집 대상이 아니다.

토큰은 사용자·출처별로 분리한다. Fernet으로 암호화하며 서버 AUTH_SECRET에서 용도 구분 HMAC-SHA256 키를 파생한다. 사용자 UUID와 provider를 암호문 내부에 포함해 행 간 암호문 교체를 거부한다. AUTH_SECRET을 변경하면 기존 토큰을 다시 저장해야 한다. 키가 없으면 저장을 거부한다.

조회와 worker는 해당 사용자의 저장 토큰을 우선하고, 없으면 기존 CIVITAI_TOKEN/HF_TOKEN 서버 설정을 사용한다. HF 공개 모델은 무토큰 접근을 유지한다. 저장 변경은 다음 조회와 worker 작업부터 적용하며 진행 중인 전송은 시작할 때 읽은 토큰으로 끝낸다.
