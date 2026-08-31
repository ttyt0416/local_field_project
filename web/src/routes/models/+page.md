# CIVITAI 다운로드 화면

메뉴와 화면 이름은 정확히 `CIVITAI 다운로드`다. 체크포인트, Diffusion Model, LoRA, 텍스트 인코더, VAE, 임베딩 중 하나를 선택하고 Civitai model 링크, version ID 또는 version 링크를 조회한 뒤 파일을 선택한다. Model page 링크는 최신 호환 version을 기본으로 보여주며, 호환 version이 여러 개면 결과 card의 `버전 선택` modal에서 이름, base model, 공개일을 보고 다른 version으로 바꿀 수 있다. Version을 바꾸면 다운로드 파일 목록과 기본 파일도 함께 갱신된다.

브라우저는 파일을 직접 받지 않는다. 다운로드 버튼은 항상 폴더 modal을 열고 `GET /models/folders`의 root·기존 폴더를 선택하거나 `+ 새 폴더`로 선택한 parent 아래에 폴더 하나를 만든 뒤 `POST /models/civitai/download`로 server job을 생성한다. Full checkpoint는 `checkpoints`, split diffusion model은 `diffusion_models`, LoRA는 `loras`, text encoder는 `text_encoders`, VAE는 `vae`, embedding은 `embeddings`에 저장된다. Illustrious는 checkpoint·LoRA·embedding 각각의 `Illustrious` subfolder를 선택한다.

화면의 `다운로드 중인 콘텐츠`는 `GET /models/downloads?active_only=true`로 `queued`와 `downloading`만 표시한다. `중단` 성공 시 항목을 즉시 제거하고 `.part` 임시 파일도 삭제한다. enqueue 성공 후 URL, lookup, 파일과 폴더 선택을 초기화하며 URL 변경 시 이전 lookup을 즉시 무효화한다. 실제 download request는 화면의 mutable URL이 아니라 조회된 version ID를 사용한다. 서버 worker가 브라우저와 무관하게 다운로드를 계속한다.

설치된 모델은 `GET /models/installed`에서 읽어 표시한다. 각 모델의 삭제 버튼은 확인 후 `DELETE /models/installed/{model_type}/{filename}`을 호출하며, 서버가 허용된 모델 폴더 내부의 파일만 삭제한다. Civitai token과 download URL은 frontend에 노출하지 않는다.
