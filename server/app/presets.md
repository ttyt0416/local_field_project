# 프리셋 API

`/presets`는 사용자별 `t2i`와 `video` 프리셋을 제공한다. 목록 조회와 삭제는 `type` query로 타입을 구분하고, 생성·수정 payload에도 타입을 포함한다. `t2i`는 기존 이미지 생성 필드를, `video`는 prompt·mode(`i2v`, `fl2v`, `r2v`)·크기·duration·seed를 저장한다. 저장 값이 없는 요청은 거부하며, 기존 사용자별 ownership과 타입별 기본 프리셋 정책을 유지한다.
