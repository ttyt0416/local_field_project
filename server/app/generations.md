# Generation active API

`GET /generation/active`는 공용 `image_generations`, `video_generations`, `three_d_generations`, `music_generations` 중 `queued`·`processing` row만 반환한다. 응답은 `created_at`과 현재 `elapsed_seconds`도 포함하며 3D row는 현재 `stage`도 포함한다. video sequence row는 aggregate `progress`와 0-based `segment_index`, total `segment_count`도 반환한다. 프런트는 이 DB snapshot으로 새로고침 뒤 generation ID, client ID, mode·stage와 SSE endpoint를 복구한다.

응답은 사용자 소유 row만 포함하며, 완료·실패 row는 반환하지 않는다. 실제 작업 완료와 결과 저장은 서버 generation worker가 담당하고, 상태 변경은 generation event broker를 통해 generation별 SSE로 push한다.

3D active 응답은 generation_mode(mesh 또는 rigging)를 포함한다. 프런트는 이를 이용해 탭별로 작업을 구분하며 SSE·취소 URL은 기존 3D 경로를 공유한다.

## 공용 사용

Local Field 계정 인증과 사용자별 소유자 인자를 제거하고 콘텐츠·작업을 공용으로 처리한다. 외부 서비스의 API 토큰과 기존 오류 기록은 유지한다.
