# Civitai model downloads

`/models/civitai/lookup`는 숫자 version ID, Civitai version/download 링크, `civitai.com` 또는 `civitai.red`의 `/models/{model_id}` 링크를 받는다. Model page 링크 자체는 fetch하지 않고 model ID를 추출해 official `civitai.com/api/v1/models/{id}`만 호출한다. `modelVersionId` query가 있으면 해당 version을 우선하고, 없으면 선택한 Local Field 모델 타입과 ComfyUI 확장자에 맞는 version을 `publishedAt` 최신순으로 정렬해 첫 version을 기본 선택한다. 응답의 `versions`는 변경 가능한 호환 version 목록이며 선택된 version의 파일과 `selected_file_index`를 함께 반환한다. 숫자 ID는 기존 계약대로 version ID다.

`POST /models/civitai/download`는 선택한 Civitai 파일의 타입과 ComfyUI 지원 확장자를 검증한 뒤 `model_downloads`에 `queued` 작업을 만든다. `subfolder`는 선택한 모델 타입 폴더 아래에 이미 존재하는 안전한 상대 경로여야 하며, 비워 두면 해당 폴더 바로 아래에 저장한다. 같은 사용자·version·모델 타입·파일의 active job은 중복 생성하지 않는다. `POST /models/downloads/{id}/cancel`은 `queued` 또는 `downloading` 작업을 `cancelled`로 바꾸고 `.part` 임시 파일을 삭제한다. 실패하거나 중단된 작업은 `POST /models/downloads/{id}/retry`로 다시 큐에 넣을 수 있다. Civitai token은 backend 환경에서만 사용하며 DB job, API response, frontend로 전달하지 않는다. 기존 파일은 덮어쓰지 않는다.

서버 startup worker는 queued 작업을 claim하고 Civitai 파일을 `COMFYUI_MODELS_PATH` 아래의 model type 폴더에 `.part` 파일로 받는다. 현재 폴더 매핑은 `checkpoint=checkpoints`, `diffusion_model=diffusion_models`, `lora=loras`, `text_encoder=text_encoders`, `vae=vae`, `embedding=embeddings`다. Anima·MiniMax 계열 checkpoint는 split UNET이므로 `diffusion_model`을 선택하고 Illustrious full SDXL checkpoint는 `checkpoint`를 선택한다. 사용자가 입력한 `subfolder`는 이 폴더 아래의 안전한 상대 경로로만 처리한다. 하위폴더는 `..`, 절대 경로, backslash, 제어문자, symbolic link를 거부하며 모델 root 밖으로 resolve되는 경로를 허용하지 않는다. 서버 재시작이나 전송 오류 뒤에는 같은 `.part` 파일을 HTTP Range로 이어받고, 사용자가 중단한 경우에는 worker가 해당 `.part` 파일을 삭제한다. Civitai SHA256이 있으면 검증한 뒤 `os.replace`로 최종 파일을 만든다. worker는 브라우저 연결과 무관하게 동작하며 상태와 진행 바이트는 `model_downloads`에 저장한다.

`GET /models/folders`는 모델 종류별 기존 폴더를 반환하고 hidden 경로는 제외한다. `POST /models/folders`는 선택한 기존 parent 아래에 slash·backslash·hidden name이 없는 단일 폴더 이름만 새로 만든다. symlink와 root 탈출, 존재하지 않는 parent, 중복 폴더를 거부한다.

`GET /models/folders/info`는 model_type·subfolder를 받아 전체 하위 파일 수·하위 폴더 수·용량·revision·활성 다운로드 여부를 반환한다. 확장자와 숨김 여부에 관계없이 포함하며 하위 symlink는 링크 자체만 집계하고 대상을 따라가지 않는다. `POST /models/folders/{model_type}/rename`은 subfolder·name으로 같은 부모 안에서 폴더 이름을 변경한다. 하위 파일을 유지하며 기존 폴더를 덮어쓰지 않는다. `DELETE /models/folders/{model_type}/{subfolder}`는 info에서 받은 revision query가 현재 내용과 같을 때만 하위 전체를 삭제한다. revision은 상대 경로·파일 종류·크기·수정 시각·inode 정보를 해시하며 확인 이후 변경이 있으면 409로 거절한다. 디렉터리 삭제는 symlink 대상을 따라가지 않는 shutil.rmtree를 사용한다. 두 변경 API는 모델 종류 기본 폴더·hidden·traversal·symlink 경로를 거부한다.

모델 저장소는 현재 단일 API 프로세스로 실행하며 폴더 변경·파일 변경·새 폴더·다운로드 enqueue·재시도를 공용 RLock으로 직렬화한다. 폴더 하위에 queued/downloading 작업이 있으면 사용자와 무관하게 변경·삭제를 막는다. 과거 failed/cancelled 다운로드의 경로 기록은 유지하며 삭제되거나 이름이 바뀐 저장 폴더로 재시도하면 새 위치를 선택하도록 409로 안내한다. 취소된 worker가 폴더를 재생성하지 않도록 mkdir 전에 작업 상태를 같은 lock 안에서 확인한다. API 호출·오류는 기존 전역 middleware가 DB에 기록한다.

`GET /models/installed`는 여섯 ComfyUI 모델 폴더의 현재 파일 목록을 반환하고, `DELETE /models/installed/{model_type}/{filename}`는 허용된 모델 폴더 안의 설치 파일을 삭제한다. 삭제 endpoint는 로그인과 모델 확장자를 확인하고 경로 탈출을 차단한다. `GET /models/downloads`는 로그인한 사용자의 최근 download job을 반환하며 `active_only=true`이면 `queued`와 `downloading`만 반환한다. 실제 Civitai 파일 다운로드는 server worker가 수행하며, 이 구현 검증에서는 대용량 모델 파일을 받거나 ComfyUI inference를 실행하지 않는다.


MOSS·MOSS Image·MOSS Image SFT·MOSS-Image-SFT-8-steps-dmd 등의 base model 표기는 MOSS family로 통합한다. MOSS checkpoint는 Diffusion Model로 분류하고, 타입별로 기존 MOSS 폴더가 있으면 자동 선택한다. LoRA는 loras/MOSS를 공통 저장 폴더로 사용한다.
