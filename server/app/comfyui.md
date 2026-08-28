# ComfyUI 이미지 저장

이미지 생성 요청은 ComfyUI `/prompt` 제출과 `image_generations` active row 생성 후 `202`를 반환한다. 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업의 ComfyUI history를 확인한다. 완료되면 첫 번째 결과 이미지를 독립 Storage API에 업로드하고 반환된 파일 ID를 `image_generations.storage_file_id`에 저장한다. 프런트는 `/generation/image/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트를 받으며, 화면을 떠나도 서버 처리는 계속된다.

Storage가 설정된 생성 결과는 만료 읽기 URL을 사용한다. 기존 생성 데이터나 Storage 설정이 없는 환경은 기존 Local Field 이미지 프록시를 사용해 개발 환경과 기존 데이터를 유지한다. 이미지 조회 endpoint도 Storage 파일 ID가 있으면 서명 URL로 임시 리다이렉트한다.

LoRA 선택의 기본 strength는 `1.0`이며, 생성 seed는 PostgreSQL `BIGINT`에 저장 가능한 signed 64-bit 범위로 제한한다.
