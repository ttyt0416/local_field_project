# 공통 오류·기록 유틸

`record_exception`은 예외 객체를 받아 원인 종류·원문·traceback·errno·파일 경로·프로세스 반환 코드·stderr/stdout·JSON 파싱 원문을 보존한다. `raise ... from None`의 context도 추적한다. 같은 예외 체인은 한 번만 큐에 넣는다. provider_response는 체인에서 찾아 보존한다.

`record_remote_error`는 ComfyUI execution_error/history 및 SkinTokens 응답의 실제 exception_type·exception_message·traceback을 포함한 응답 전체를 저장한다. `audit_stream`은 응답 시작 이후 스트리밍 예외도 기록한 뒤 원래 예외를 전파한다. `audit_error_response`는 예외 없이 반환된 HTTP 오류의 본문을 원래 스트림을 변경하지 않고 복사한다.

기록 함수는 await·DB 저장 대기를 하지 않는다. API/인증, 오류, 웹 기록은 각각 최대 4,096건의 큐와 daemon 스레드를 사용한다. `put_nowait`로 전달하며 큐 초과·DB 실패·HTTP 본문 읽기 실패는 원래 기능으로 전파하지 않는다. 오류 HTTP 본문은 기록 스레드에서 최대 2 MiB까지 읽고 초과 여부를 남긴다. 직접 오류 응답 본문도 2 MiB와 초과 표시를 사용한다. 예외 메시지의 기존 1,000자 제한은 제거했다.

기록은 best effort다. 큐 초과·프로세스 강제 종료·저장 실패 시 유실될 수 있으며 저장 실패는 stderr에 남긴다. 기능을 기다리게 하는 재시도·동기 flush는 두지 않는다. DB 자체가 실패하면 같은 DB에 그 실패를 반복 저장하지 않는다.

비밀번호·인증 헤더·API 토큰·서명 URL의 자격 정보는 가린다. traceback의 로컬 변수와 검증 실패 입력값은 저장하지 않는다. `completion_tokens` 등 진단용 토큰 사용량은 유지한다. DB에서 표현할 수 없는 NUL 문자는 리터럴 `\u0000`으로 보존한다.

## 함수별 확인 경로

각 catch의 복구/전파 흐름을 확인하고, 예외가 HTTP 경계까지 전파되는 함수는 공통 경계에서 원인 체인을 기록하도록 했다. 예외를 소비하는 아래 함수는 호출 위치에 직접 기록을 연결했다.

| 모듈 | 함수 및 경로 | 기록 방식 |
| --- | --- | --- |
| main | audit_api_requests, audit_handled_exception, audit_validation_exception | HTTP 원인 체인·검증 내역·직접 오류 Response 본문 |
| model_downloads | installed_models, _suggested_subfolder, _run_model_download_worker, run_model_download_worker | stat·폴더 탐색 복구, 다운로드/초기화/작업 조회 오류 원문 |
| generation_worker | reconcile_active_generations의 이미지·영상·음악·3D 분기, _watch_progress, run_generation_reconciler | 각각의 사용자·prompt_id와 원인 예외 |
| comfyui | record_comfy_progress, stream_comfy_progress, _queue_position, _stream_generation_events, _history_generation_status | 원격 실행 오류·JSON 파싱·복구·SSE 오류 |
| music | music_options, _stream_events, _history_status | 준비 상태 복구·SSE·원격 실행 오류 |
| three_d | three_d_options, _stream_events, _history_status | 준비 상태 복구·SSE·원격 실행 오류 |
| video | _stream_video_events, _history_status, _delete_internal_sequence_files, _sync_video_output의 취소 복구 | SSE·원격 실행 오류·정리·취소 오류 |
| rigging | request_worker, create_rigging, _sync_status | 자격 파일·HTTP·네트워크·JSON·원격 실패 원문. ack 복구도 request_worker에서 기록 |
| animadex | _read_thumbnail, _read_url, sync_catalogue | 재시도 전 연결 오류·HTTP 본문·네트워크·가져오기 오류 |
| animadex_assets | read_state, sync_thumbnails 내부 download | JSON/파일 복구·썸네일 검증/저장 실패 |
| vault | edit_vault_video, edit_vault_image, _generation_file_size | 원래 편집 오류와 별도로 정리·크기 조회 실패 보존 |
| uploads | reusable_media, _remove_storage_file | 미리보기·정리 복구 실패 |
| auth | _verify_password | 잘못 저장된 해시 파싱 오류 |
| media_editing | _run | 비정상 종료 stderr/stdout/returncode를 cause에 보존 |
| hugging_face | open_download | 실패 HTTP 본문을 닫지 않고 기록 경계로 전달 |

storage의 upload_file/download_file/file_size/delete_file/_request_json, hardware의 조회/파싱, danbooru의 외부 요청, comfyui/video의 HTTP 및 vLLM 요청, 업로드·보관함·프리셋·저장 프롬프트·태그 조회의 전파 예외는 공통 HTTP 경계 또는 생성 워커에서 보존한다. 일반 UI 문구로 감싸도 원래 cause/context를 읽는다.

정상 제어 흐름인 폴링/heartbeat 타임아웃, 사용자 취소, 리디렉션, 이미 없는 객체 삭제, HEAD 미지원 후 Range 조회, 중복 다운로드 충돌, 선택 불가 버전/경로 거르기, 숫자·날짜 선택값 기본 처리, 선택적 토큰 검증 실패는 장애로 중복 기록하지 않는다. 최종 API 실패는 HTTP 경계에서 기록한다.
