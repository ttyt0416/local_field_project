# 서버 설정

`DEFAULT_VLLM_MODEL`은 production에서 사용하는 Hugging Face 모델의 served model name과 일치해야 한다. 현재 기본 모델은 `pekkAi/G4-MeroMero-26B-A4B-it-uncensored-heretic-NVFP4`이며, `VLLM_URL`과 `VLLM_MODEL` 환경 변수로 재정의할 수 있다.

Civitai 모델 다운로드는 `CIVITAI_TOKEN` 환경 변수만 backend에서 읽는다. token은 API response, DB, log, frontend에 전달하지 않는다. `COMFYUI_MODELS_PATH`는 ComfyUI의 `models` 폴더를 가리키며 기본값은 `/comfyui-models`다. `COMFYUI_URL` 기본값은 isolated worker가 아닌 shared ComfyUI `http://host.docker.internal:8188`이다.

Hugging Face 공개 모델은 토큰 없이 받는다. 제한·비공개 저장소는 서버 환경의 `HF_TOKEN`을 선택적으로 사용하며 production에서는 server/.env.production으로 주입할 수 있다. 토큰은 Hugging Face 본체 요청에만 보내고 CDN·프런트엔드·DB에는 전달하지 않는다.
