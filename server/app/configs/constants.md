# 서버 설정

`DEFAULT_LLM_MODEL`은 vLLM의 served model name과 일치해야 한다. 현재 기본 모델은 `qwen3.8-27b-fable-nvfp4`이며, `LLM_URL`과 `LLM_MODEL` 환경 변수로 재정의할 수 있다.

Civitai와 Hugging Face 다운로드 토큰은 공용 암호화 저장소에서 읽으며 원문 토큰을 환경 설정에 두지 않는다. `COMFYUI_MODELS_PATH`는 ComfyUI의 `models` 폴더를 가리키며 기본값은 `/comfyui-models`다. `COMFYUI_URL` 기본값은 isolated worker가 아닌 shared ComfyUI `http://host.docker.internal:8188`이다.

Hugging Face 공개 모델은 토큰 없이 받는다. 제한·비공개 저장소는 다운로드 관리에 저장한 공용 토큰을 사용한다. 토큰은 Hugging Face 본체 요청에만 보내고 CDN·프런트엔드·다운로드 작업 기록에는 전달하지 않는다.

`TOKEN_ENCRYPTION_SECRET`은 공용 서비스 토큰의 암호화 전용 키다. 로그인 인증 키와 JWT 설정은 사용하지 않는다.

## 공용 사용

Local Field 계정 인증과 사용자별 소유자 인자를 제거하고 콘텐츠·작업을 공용으로 처리한다. 외부 서비스의 API 토큰과 기존 오류 기록은 유지한다.

생성용 기본 모델은 Qwen3.8-27B Fable Cold Fusion NVFP4다. 이미지·동영상·음악 강화는 공통 LLM_URL/LLM_MODEL을 사용하며, 임베딩의 EMBEDDING_URL/EMBEDDING_MODEL/1024차원 설정은 별도로 유지한다.

LLM_VISION_ENABLED는 기본 true이며 영상 강화의 labeled image preview 전달을 제어한다. 임베딩 설정은 별도다.
