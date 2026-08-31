# ComfyUI 이미지 저장

이미지 생성 요청은 ComfyUI `/prompt` 제출과 `image_generations` active row 생성 후 `202`를 반환한다. 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업의 ComfyUI history를 확인한다. 완료되면 첫 번째 결과 이미지를 독립 Storage API에 업로드하고 반환된 파일 ID를 `image_generations.storage_file_id`에 저장한다. 생성 row의 `created_at`, `completed_at`, `elapsed_seconds`를 함께 저장하며, 프런트는 `/generation/image/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트와 timing 값을 받는다. 화면을 떠나도 서버 처리는 계속된다.

Storage가 설정된 생성 결과는 만료 읽기 URL을 사용한다. 기존 생성 데이터나 Storage 설정이 없는 환경은 기존 Local Field 이미지 프록시를 사용해 개발 환경과 기존 데이터를 유지한다. 이미지 조회 endpoint도 Storage 파일 ID가 있으면 서명 URL로 임시 리다이렉트한다.

`POST /generation/image/{prompt_id}/cancel`은 소유권을 확인한 뒤 실행 중 prompt에는 targeted `/interrupt`, pending prompt에는 해당 ID만 queue delete를 요청한다. DB, SSE, 전역 job store가 모두 `cancelled` terminal 상태를 사용해 polling과 대기 promise를 종료한다.

lora strength는 기본값 `1.0`이고 별도 최대·최소 범위를 적용하지 않는다. 생성 seed는 PostgreSQL `BIGINT`에 저장 가능한 signed 64-bit 범위로 제한한다.

공통 Comfy progress state는 현재 실행 node ID도 보존한다. image/video caller는 기존 progress 계약을 그대로 사용하고, TRELLIS.2 router는 node ID를 background cleanup·structure·shape·texture·mesh stage로 매핑한다.
