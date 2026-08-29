# Civitai model downloads

`/models/civitai/lookup`는 Civitai `model-versions/{id}`를 조회하고 선택한 Local Field 모델 타입에 맞는 파일 목록과 `selected_file_index`를 반환한다. `source`에는 숫자 version ID 또는 `modelVersionId`가 포함된 Civitai 링크를 사용한다.

`POST /models/civitai/download`는 선택한 Civitai 파일의 타입과 ComfyUI 지원 확장자를 검증한 뒤 `model_downloads`에 `queued` 작업을 만든다. 같은 사용자·version·모델 타입·파일의 active job은 중복 생성하지 않는다. `POST /models/downloads/{id}/cancel`은 `queued` 또는 `downloading` 작업을 `cancelled`로 바꾸고 `.part` 임시 파일을 삭제한다. 실패하거나 중단된 작업은 `POST /models/downloads/{id}/retry`로 다시 큐에 넣을 수 있다. Civitai token은 backend 환경에서만 사용하며 DB job, API response, frontend로 전달하지 않는다. 기존 파일은 덮어쓰지 않는다.

서버 startup worker는 queued 작업을 claim하고 Civitai 파일을 `COMFYUI_MODELS_PATH` 아래의 `checkpoints`, `loras`, `text_encoders`, `vae`, `embeddings` 폴더에 `.part` 파일로 받는다. 서버 재시작이나 전송 오류 뒤에는 같은 `.part` 파일을 HTTP Range로 이어받고, 사용자가 중단한 경우에는 worker가 해당 `.part` 파일을 삭제한다. Civitai SHA256이 있으면 검증한 뒤 `os.replace`로 최종 파일을 만든다. worker는 브라우저 연결과 무관하게 동작하며 상태와 진행 바이트는 `model_downloads`에 저장한다.

`GET /models/installed`는 다섯 ComfyUI 모델 폴더의 현재 파일 목록을 반환하고, `DELETE /models/installed/{model_type}/{filename}`는 허용된 모델 폴더 안의 설치 파일을 삭제한다. 삭제 endpoint는 로그인과 모델 확장자를 확인하고 경로 탈출을 차단한다. `GET /models/downloads`는 로그인한 사용자의 최근 download job을 반환한다. 실제 Civitai 파일 다운로드는 server worker가 수행하며, 이 구현 검증에서는 대용량 모델 파일을 받거나 ComfyUI inference를 실행하지 않는다.
