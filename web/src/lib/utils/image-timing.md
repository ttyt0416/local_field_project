# 이미지 표시 진단

기존 `api_audit_logs`와 `/web/api-timings`를 사용하며 이미지 로딩·캐시·재시도·시간 제한 동작을 변경하지 않는다. `method=IMG`, `source=browser`, `timing_context.category=image`로 찾는다. 서명 URL은 query·fragment·사용자명·비밀번호를 제거하고 파일 ID와 경로만 기록한다. data/Blob URL의 원문과 이미지 바이트는 기록하지 않는다.

`generation_result_received`는 생성 완료 SSE를 브라우저가 받은 시점이다. `prompt_id`, `generation_id`, `file_id`, `has_image_url`로 서버의 `image.finalize`, `storage.read_url`, `image.result_delivery`와 연결한다. 서버의 result_delivery는 SSE 직렬화 시점이며 실제 네트워크 전달 완료 시점은 아니다.

`image_load`는 소스 처리 시작부터 native `load`·`error` 또는 컴포넌트 해제까지 같은 request_id 한 행을 갱신한다. inline과 gallery는 별도 요청으로 구분한다. 시작 직후와 10초·30초에 미완료 상태를 기록한다. 지연 체크는 요청을 중단하지 않으며 실제 타임아웃으로 표시하지 않는다. 종료 이벤트는 한 번만 기록하고 타이머·관찰자·리스너를 해제한다. 미완료 상태로 화면을 떠나면 cancelled다.

| timing_context 필드 | 의미 |
| --- | --- |
| source_ready_ms / blob_bytes | 외부 src 또는 서버 Blob 준비까지의 시간과 Blob 크기 |
| first_visible_ms / in_viewport / loading | viewport 첫 진입 시점·최근 IntersectionObserver 관찰 위치·lazy 설정. 동기 레이아웃 계산은 하지 않음 |
| request_start_delay_ms | src 준비 후 브라우저 Resource Timing의 요청 시작까지. lazy·스케줄링 대기 등이 포함됨 |
| resource_duration_ms | 브라우저가 관측한 리소스 요청 전체 시간 |
| dns_ms / connect_ms / response_wait_ms / download_ms | 노출된 Resource Timing의 DNS·연결·요청부터 응답 헤더·본문 수신 구간 |
| after_response_ms | 응답 완료부터 이벤트 처리까지. 이미지 디코딩·브라우저 스케줄링 등이 포함될 수 있으며 순수 디코딩 또는 실제 paint 시간은 아님 |
| resource_timing | full, restricted, missing, unavailable. 다른 origin에서 Timing-Allow-Origin이 없으면 세부 구간·크기는 null이며 0ms로 추정하지 않음 |
| response_status / cache_state | 노출된 HTTP 상태·캐시 근거. 알 수 없는 HTTP 상태는 null 및 status_code=0, 캐시는 unknown |
| visibility_at_start / visibility / hidden_ms / document_has_focus | 숨겨진 탭·포커스 상태·관측 중 숨겨진 시간 |
| url_valid_for_ms | src 처리 시작 시점의 서명 URL 잔여 유효시간. 음수이면 이미 만료됨 |
| slow_threshold_ms / watchdog_delay_ms | 지연 기준과 백그라운드 탭 등으로 체크 타이머가 늦게 실행된 시간 |
| failure_phase / error_type | Blob 준비 실패와 native 이미지 로딩·디코딩 실패 구분 |

Resource Timing은 현재 src 할당 이후의 img entry만 사용해 이전 요청 시간을 잘못 재사용하지 않는다. 같은 파일의 동시 요청 병합·캐시·Blob 표시·브라우저 버퍼 누락은 missing일 수 있다. native error는 HTTP 상태를 추정하지 않고 `ImageLoadError`로 오류 DB에도 기록한다. 요청 지연과 디코딩 실패를 구분할 증거가 없으면 해당 구분은 보류한다.

최근 이미지 진단 조회:

```sql
SELECT requested_at, source, method, path, outcome, duration_ms,
       parent_request_id, timing_context
FROM api_audit_logs
WHERE requested_at > now() - interval '30 minutes'
  AND (timing_context->>'category' = 'image' OR path = 'storage.read_url')
ORDER BY requested_at;
```

같은 `file_id` 또는 `prompt_id`와 parent_request_id를 기준으로 확인한다. 로그 전송은 기다리지 않으며 기록 실패가 이미지 표시를 막지 않는다. 기존 로그에는 없던 브라우저 측정값을 소급해서 채우지 않는다.
