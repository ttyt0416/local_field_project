# 다운로드 관리 화면

메뉴와 화면 이름은 `다운로드 관리`이며 기존 `/models` 경로를 유지한다. 공용 Tab으로 Civitai와 Hugging Face를 선택한다. Civitai 탭의 lookup 전에는 체크포인트, Diffusion Model, LoRA, 텍스트 인코더, VAE, 임베딩 tab으로 fallback type을 고를 수 있다. Civitai lookup은 받은 type을 감지해 type이 다르면 selected tab을 자동 변경한다. `LORA`·`LoCon`·`DoRA`는 LoRA, `Checkpoint`의 base model이 Anima·MiniMax면 Diffusion Model, 그 밖의 Civitai checkpoint는 Checkpoint로 선택한다. lookup 결과의 파일·version 선택은 그 auto type을 사용한다.

base model에 Anima, MiniMax, Illustrious가 있고 selected model type root 아래에 같은 family 이름의 folder가 있으면, 가장 shallow한 matching relative folder를 자동 선택한다. nested folder도 대상이며, matching folder가 없으면 root `전체`를 선택한다. 사용자는 folder dialog에서 자동 type과 folder를 다시 바꿀 수 있다.

브라우저는 파일을 직접 받지 않는다. 다운로드 버튼은 공용 ModelFolderPicker를 열고 `GET /models/folders`에서 현재 model type root의 folder tree를 탐색한다. 모델 종류 버튼은 root를 선택하고, 하위 folder button은 그 folder를 선택하면서 안으로 이동한다. `상위 폴더`로 되돌아갈 수 있고, `새 폴더`는 현재 위치 아래에 한 level을 만든다. 같은 동작을 반복해 arbitrary nested folder를 만든다. `POST /models/civitai/download`는 선택한 relative subfolder만 받아 server job을 생성한다. Full checkpoint는 `checkpoints`, split diffusion model은 `diffusion_models`, LoRA는 `loras`, text encoder는 `text_encoders`, VAE는 `vae`, embedding은 `embeddings`에 저장된다. 모델 종류 메타데이터는 파일 관리와 model-storage 타입 모듈을 공유한다. Illustrious는 checkpoint·LoRA·embedding 각각의 `Illustrious` subfolder를 선택한다.

공통 `다운로드 중인 콘텐츠`는 `GET /models/downloads?limit=100`에서 queued/downloading만 표시하고 출처·모델 종류와 해당 version 또는 repo/commit을 구분한다. 화면에서 추적 중이던 작업이 failed로 바뀌면 error_message를 Toast와 공통 inline 안내로 표시한다. 지난 실패 이력은 새 방문 때 다시 알리지 않는다. 오래된 polling 응답이 새 enqueue·중단 결과를 덮어쓰지 않도록 로컬 revision을 확인한다. `중단` 성공 시 항목을 즉시 제거하고 `.part` 임시 파일도 삭제한다. enqueue 성공 후 URL, lookup, 파일과 폴더 선택을 초기화하며 URL 변경 시 이전 lookup을 즉시 무효화한다. 실제 download request는 화면의 mutable URL이 아니라 조회된 version ID를 사용한다. 서버 worker가 브라우저와 무관하게 다운로드를 계속한다.

이 페이지는 설치 파일 목록을 요청하지 않으며 모델 파일의 이동·삭제도 제공하지 않는다. 해당 기능은 사이드바의 별도 `/files` 파일 관리로 분리한다. 화면 상단에서 파일 관리로 이동할 수 있다. Civitai token과 download URL은 frontend에 노출하지 않는다. 다운로드 목록의 새로고침과 polling 실패는 catch 후 Toast로 표시한다.


MOSS LoRA의 폴더 선택·설치 목록 필터는 공통 MOSS 폴더를 사용한다. Civitai base model의 MOSS Image/SFT/DMD 변형도 MOSS family로 자동 분류한다.

Hugging Face 탭은 공용 HuggingFaceDownload 패널을 사용한다. 저장소·파일·폴더 링크와 선택 리비전을 조회해 모델 파일을 검색·선택하고 공용 폴더 모달로 저장 위치를 선택한다. 조회한 commit에 고정해 enqueue하고, 두 출처의 작업은 탭 변경 후에도 같은 진행 목록에 표시한다. 작업 요청 중 탭 전환을 막으며 Civitai URL·타입·탭 변경 후 이전 조회 응답은 적용하지 않는다.
