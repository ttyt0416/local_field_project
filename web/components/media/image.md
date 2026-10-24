# 이미지 미디어 소스

선택적인 onerror callback은 server Blob 요청 실패 메시지를 부모에게 전달한다. 로컬 카탈로그는 이 callback으로 통신 오류 Toast를 표시한다. callback을 전달하지 않는 기존 사용처의 동작은 유지한다.

Blob URL이 준비되기 전에는 img를 만들지 않는다. 빈 src가 문서를 이미지로 요청해 failed 상태를 먼저 고정하던 문제를 방지한다. 실제 디코딩 실패도 onerror callback으로 알린다.

`ImageMedia`는 Local Field 인증이 필요한 상대 서버 URL과 독립 Storage의 절대 URL을 구분한다.

`server` 소스는 기존 인증 Blob 요청을 사용하고, `external` 소스는 만료된 Storage URL을 직접 이미지로 로드한다. 두 원격 소스 모두 동일한 로딩 shimmer와 확대 갤러리 동작을 유지한다. Storage signed URL은 서버에서 짧게 재사용되어 브라우저의 기본 이미지 캐시가 같은 파일에 적용될 수 있다. 확대 갤러리는 100%에서 125%씩 최대 400%까지 확대·축소하고, 갤러리 이동 시 100%로 초기화한다.
