# 이미지 생성 결과 표시

이미지 생성 응답 URL이 독립 Storage의 절대 URL이면 `ImageMedia`에 `external` 소스로 전달한다. Storage 연동이 비활성화된 개발 환경에서 반환되는 기존 상대 URL은 `server` 소스로 처리한다.
