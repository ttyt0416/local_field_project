# 이미지 미디어 소스

`ImageMedia`는 Local Field 인증이 필요한 상대 서버 URL과 독립 Storage의 절대 URL을 구분한다.

`server` 소스는 기존 인증 Blob 요청을 사용하고, `external` 소스는 만료된 Storage URL을 직접 이미지로 로드한다. 두 원격 소스 모두 동일한 로딩 shimmer와 확대 갤러리 동작을 유지한다.
