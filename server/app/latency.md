# API 레이턴시

`ApiTimer`는 monotonic `perf_counter`로 밀리초를 측정한다. 실제 요청 시작 UTC 시각을 별도로 저장하며, DB 큐 대기 시간은 처리 시간에 포함하지 않는다. 기존 `audit.fire_and_forget`과 `database.record_api_call`을 재사용하고 기록 실패를 원래 기능에 전파하지 않는다.

| 필드 | 의미 |
| --- | --- |
| source | server: 서버 수신 API, upstream: 서버의 외부 호출, browser: 브라우저에서 관측한 API 호출 |
| request_id | 헤더·첫 본문·종료 기록을 한 행으로 갱신하는 UUID |
| parent_request_id | 외부 호출을 유발한 서버 요청 UUID. 독립 백그라운드 작업에는 없을 수 있다 |
| requested_at / finished_at | 실제 시작·종료 시각. 열린 연결은 finished_at이 비어 있다 |
| headers_ms | 서버가 응답 헤더를 보내거나 외부·브라우저 요청이 헤더를 받은 시점까지의 시간 |
| first_byte_ms | 애플리케이션이 처음 전달/수신한 비어 있지 않은 본문 청크 시점. 소켓의 물리적인 첫 바이트 측정값은 아니다 |
| duration_ms | 응답 본문 전달/읽기 또는 연결 종료까지의 전체 시간 |
| outcome | in_progress, completed, http_error, error, timeout, cancelled, disconnected, incomplete |

`ApiTimingMiddleware`는 ASGI send/receive를 그대로 전달하면서 일반 응답, 오류, SSE, 파일 응답, 클라이언트 연결 종료를 측정한다. SSE는 헤더와 첫 청크를 연결이 열린 동안 저장하고 종료 시 전체 시간을 같은 행에 반영한다. 본문이나 헤더 내용을 변경·선소비하지 않는다. 응답 전 예외는 status 500과 실패까지의 시간을 남기며 헤더/첫 본문 시간은 비어 있을 수 있다.

`timed_urlopen`은 원래 opener에 원래 인자를 전달한다. `TimedResponse`는 응답 속성과 read/close/context 동작을 보존한다. 전체 read 또는 EOF/close에서 종료를 기록하고 연결·본문 읽기 실패 및 HTTP 오류도 측정한 뒤 원래 예외를 전파한다. 다운로드 전송 시간에는 소비자가 청크를 읽는 간격과 backpressure가 포함된다. 진단용 HTTP 오류 본문을 나중에 읽는 오류 기록 스레드 시간은 포함하지 않는다. 수동 리디렉션은 각 홉을 개별 기록하며 자동 리디렉션은 opener 전체 응답 시간으로 기록한다.

ComfyUI JSON·바이트·이미지 업로드, vLLM, 영상 파일 업로드, 스토리지 업로드/읽기/URL/HEAD/Range/삭제, Civitai 메타데이터·다운로드, Hugging Face 메타데이터·다운로드, 임베딩, 하드웨어, SkinTokens, AnimaDex 일반 요청·재사용 HTTPS 연결 각각에 적용한다. WebSocket은 핸드셰이크 101까지의 시간, 첫 메시지 시간, 전체 연결 시간을 구분한다.

`api_user`는 다운로드·생성 워커의 사용자 정보를 to_thread 호출에 전달하고 원래 context를 복원한다. 스토리지 요청은 독립 스레드에서도 X-Owner-ID로 사용자 정보를 보존한다. 외부 URL에는 query, fragment, 사용자명·비밀번호를 저장하지 않는다.

새 요청부터 측정한다. 기존 로그의 누락된 시간은 추정해서 채우지 않는다. 기록은 기존 큐 정책에 따른 best effort이며 DB 장애·큐 초과·프로세스 강제 종료 시 유실될 수 있다.
