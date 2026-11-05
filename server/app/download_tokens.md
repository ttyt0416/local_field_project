# 다운로드 API 토큰

`/models/tokens`는 로그인 없이 Civitai/Hugging Face의 공용 API 토큰 등록 상태를 조회하고 PUT/DELETE로 저장·삭제한다. provider별 한 개의 암호문과 갱신 시각을 저장하며 토큰 원문·암호문은 응답에 포함하지 않는다. 요청 본문과 인증 헤더는 감사 로그에 저장하지 않는다.

Fernet 키는 `TOKEN_ENCRYPTION_SECRET`에서 기존 용도 구분 HMAC-SHA256 방식으로 파생한다. 암호문에는 provider와 token만 포함하고 계정 식별자는 저장하지 않는다. provider가 다른 암호문이나 변조된 암호문은 거부한다. 키가 없으면 저장을 거부한다. 기존 암호문은 DB 마이그레이션에서 읽어 계정정보 없는 형식으로 다시 암호화한다. 기존 AUTH_SECRET 값은 환경 파일에서 TOKEN_ENCRYPTION_SECRET으로 이름만 바꿔 암호화 키를 유지한다.

조회·다운로드 워커는 해당 provider의 공용 토큰을 사용한다. 저장 토큰이 없으면 빈 값을 반환하며 Hugging Face 공개 모델은 무토큰으로 받는다. 진행 중인 전송은 시작할 때 읽은 토큰으로 완료한다.
