# 서버 설정

`DEFAULT_VLLM_MODEL`은 production에서 사용하는 Hugging Face 모델의 served model name과 일치해야 한다. 현재 기본 모델은 `Huihui-Qwen3.8-27B-abliterated-NVFP4`이며, `VLLM_URL`과 `VLLM_MODEL` 환경 변수로 재정의할 수 있다.

Civitai 모델 다운로드는 `CIVITAI_TOKEN` 환경 변수만 backend에서 읽는다. token은 API response, DB, log, frontend에 전달하지 않는다. `COMFYUI_MODELS_PATH`는 ComfyUI의 `models` 폴더를 가리키며 기본값은 `/comfyui-models`다.
