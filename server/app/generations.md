# Generation active API

`GET /generation/active`는 인증된 사용자의 `image_generations`, `video_generations`, `three_d_generations` 중 `queued`·`processing` row만 반환한다. 응답은 `created_at`과 현재 `elapsed_seconds`도 포함하며 3D row는 현재 `stage`도 포함한다. video sequence row는 aggregate `progress`와 0-based `segment_index`, total `segment_count`도 반환한다. 프런트는 이 DB snapshot으로 새로고침 뒤 generation ID, client ID, mode·stage와 SSE endpoint를 복구한다.

응답은 사용자 소유 row만 포함하며, 완료·실패 row는 반환하지 않는다. 실제 작업 완료와 결과 저장은 서버 generation worker가 담당하고, 상태 변경은 generation event broker를 통해 generation별 SSE로 push한다.
