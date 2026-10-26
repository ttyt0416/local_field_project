# ComfyUI 이미지 저장

이미지 생성 요청은 ComfyUI `/prompt` 제출과 `image_generations` active row 생성 후 `202`를 반환한다. 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업의 ComfyUI history를 확인한다. 완료되면 첫 번째 결과 이미지를 독립 Storage API에 업로드하고 반환된 파일 ID를 `image_generations.storage_file_id`에 저장한다. 생성 row는 사용자 원문 `prompt`를 보존하고, 개선 prompt를 실제 사용한 경우 nullable `improved_prompt`에도 별도 저장한다. 생성 row의 `created_at`, `completed_at`, `elapsed_seconds`를 함께 저장하며, 프런트는 `/generation/image/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트와 timing 값을 받는다. 화면을 떠나도 서버 처리는 계속된다.

Storage가 설정된 생성 결과는 만료 읽기 URL을 사용한다. 기존 생성 데이터나 Storage 설정이 없는 환경은 기존 Local Field 이미지 프록시를 사용해 개발 환경과 기존 데이터를 유지한다. 이미지 조회 endpoint도 Storage 파일 ID가 있으면 서명 URL로 임시 리다이렉트한다.

Image·video·3D cancel endpoint는 shared ComfyUI의 `POST /api/jobs/{prompt_id}/cancel`을 호출한다. pending job은 ComfyUI queue에서 제거되고, running job은 해당 prompt만 interrupt한다. unknown 또는 terminal ID는 no-op이며 DB, SSE, 전역 job store는 `cancelled` terminal 상태를 사용해 polling과 대기 promise를 종료한다.

Video와 3D API workflow는 VRAM cleanup node를 포함하지 않는다. VRAM cleanup은 ComfyUI의 `LocalField VRAM Cleanup` custom output node를 graph에 직접 추가하고 Queue Prompt로 수동 실행한다. 이 node는 ComfyUI model unload, CUDA cache, IPC cache를 shared process에서 비운다.

lora strength는 기본값 `1.0`이고 별도 최대·최소 범위를 적용하지 않는다. 생성 seed는 PostgreSQL `BIGINT`에 저장 가능한 signed 64-bit 범위로 제한한다. 공통 Comfy model option reader는 legacy list schema와 ComfyUI V3 `COMBO` `{ options: [...] }` schema를 모두 처리한다.

공통 Comfy progress state는 현재 실행 node ID도 보존한다. image/video caller는 기존 progress 계약을 그대로 사용하고, TRELLIS.2 router는 node ID를 background cleanup·structure·shape·texture·mesh stage로 매핑한다.

`GET /generation/image/options?family=anima|illustrious|moss|qwen_image_2_1`는 family별 설치 모델과 기본 설정을 반환한다. Anima는 `diffusion_models/Anima/` split model과 `vae/Anima/`를 사용하고 Illustrious는 full checkpoint를 사용한다. Krea2는 신규 생성과 모델 선택에서 제거했다. 이전 Krea2 생성 기록과 프리셋 데이터는 보존한다. T2I는 Anima·Illustrious·MOSS를 지원하며 negative prompt 기본값은 빈 문자열이다. prefix는 conditioning에서만 본문 앞에 합성하고 DB에는 별도로 보관한다. Anima·MOSS prompt enhancement는 Danbooru tags와 자연어를, Illustrious는 검증된 tags만 사용한다. Anima·Illustrious I2I도 T2I와 같은 vLLM 개선 API를 사용한다.

`POST /generation/image/i2i`는 multipart payload와 소스 이미지 한 개를 받는다. local file은 submit 시에만 Storage·media_assets에 저장하고 기존 file ID는 ownership을 확인해 재사용한다. Anima·Illustrious는 `LoadImage → ImageScale → VAEEncode → KSampler`와 0~1 denoise를 유지한다.



Structured vLLM response가 `finish_reason=length`로 끝나면 server는 raw output and user prompt 없이 response schema name, configured token cap, completion token count, raw character count, JSON completion, trailing whitespace count, last schema field, parsed shot count를 warning log 한 줄로 남긴다. `_VLLMError`는 decoded provider response를 caller에 전달하며 VIDEO prompt route는 이를 Error DB에 저장한다.



## MOSS

MOSS는 T2I 전용이며 `diffusion_models/MOSS/` 아래의 체크포인트를 파일명과 관계없이 인식한다. 중첩 하위폴더를 포함한다. `text_encoders/MOSS/`의 인코더(type `moss_image`)와 `vae/MOSS/`의 VAE를 사용한다. 기본값은 Euler·SGM Uniform, 50 steps, CFG 3, shift 5이다. EmptyFlux2LatentImage에서 생성하며 i2i 요청·소스 이미지·참조 입력은 거부한다. 외부 참조 패처는 워크플로와 모델 옵션에 연결하지 않는다. 레이아웃은 선택된 원문 또는 vLLM 개선 프롬프트를 중앙 기준 JSON으로 변환하며 박스·표시할 텍스트는 그대로 보존한다. 출력 크기는 16 배수이다. DMD 버튼은 SFT에 최신 DMD LoRA 0.7, 8 steps, CFG 1을 선택한다.

참조 패처 출처는 https://github.com/silveroxides/ComfyUI-UtilsCollection 이며 설치 revision은 `52524719f934c7cc09382e2560f27f6967636255`이다. 누락된 의존성 `unifiedefficientloader==0.5.4`를 ComfyUI 환경에 추가했다.

가중치 출처: https://huggingface.co/Comfy-Org/MOSS-Image 의 SFT BF16·INT8 텍스트 인코더·small VAE와 https://huggingface.co/lodestones/MOSS-Image-SFT-8-steps-dmd 의 lora_latest.safetensors를 사용한다. Base 본체와 폐기된 DMD 전용 transformer 파일은 받지 않는다.

Qwen Image 2.1 Turbo는 qwen_image_2_1 family로 I2I·다중 참조 생성을 제공한다. 본체는 `diffusion_models/Qwen/`에서 파일명과 관계없이 선택하며 생성 그래프에 선택 경로를 그대로 전달한다. 공식 BF16 Turbo 본체, qwen3vl_8b_int8_convrot 인코더(type qwen_image), 전용 Qwen 2.1 VAE를 사용한다. TextEncodeQwenImage21에 원본을 image_1, 추가 참조를 image_2~image_10 순으로 전달한다. 원본은 선택한 출력 크기로 맞추고 추가 참조는 비율을 유지해 약 1MP·32배수로 줄인다. resolution 0으로 인코더 latent와 출력 캔버스를 일치시킨다. QwenImage21Cache auto/default와 공식 ManualSigmas [1,.978453,.95418,.926626,.89508,.845148,.704534,.414568,0], Euler·CFG 1·8 steps·Denoise 1을 사용하며 다른 조합은 업로드 전에 거부한다. 일반 KSampler 스케줄러로 대체하지 않는다. 프롬프트 개선은 공통 vLLM API에서 자연어 수정 지시를 만들고 생성 그래프는 선택된 결과를 사용한다.

출처: https://huggingface.co/Comfy-Org/Qwen-Image-2.1 / https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo / https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_turbo_image_edit.json . 모델 배포 revision은 a8342359c61979b06a8dafb1a47991fe1f30e994이다.

Qwen은 다른 이미지 모델과 같이 프롬프트 개선을 기본 끈다. 사용자가 켜고 공통 enhance-prompt API로 자연어 지시를 생성·편집하면 improved_prompt를 TextEncodeQwenImage21에 직접 전달한다. ComfyUI TextGenerate·참조 배치·조건부 스위치와 별도 PromptEnhancer 가중치를 사용하지 않는다. 원본·추가 참조는 이미지 인코더에 기존대로 전달한다. 모든 family에서 활성화 시 개선된 본문이 필수이며 I2I 소스 업로드 전에 검증한다. 비활성화 시 원문을 사용하고 Prefix는 선택된 본문 앞에 한 번만 붙인다. 활성 상태·원문·개선 본문은 생성 기록·프리셋·재생성에 따로 보존한다. options의 prompt_enhancer_available은 공통 개선 기능 지원을 뜻하며 vLLM 실시간 건강 검사는 아니다. 요청 유효성 오류는 직렬화 가능한 context 제외 형식으로 반환한다.


Illustrious 체크포인트가 설치되지 않은 경우 옵션 API는 빈 checkpoints와 빈 default_checkpoint를 반환한다. 프리셋 조회·편집은 유지하고 실제 생성 요청은 기존 모델 검증에서 422로 차단한다. ComfyUI 연결 장애는 기존 오류로 처리한다.


MOSS LoRA는 `loras/MOSS/` 및 하위폴더에서 파일명과 관계없이 선택한다. 원본 Hugging Face 저장소 이름은 MOSS-Image-SFT-8-steps-dmd이며 로컬 분류 이름과 구분한다.

## 공통 모델 폴더 검색

체크포인트·LoRA 선택과 이미지·동영상·음악·3D 자동 모델 로딩은 ComfyUI의 live object_info에서 역할별 폴더 및 하위폴더를 검색한다. 파일명 allowlist나 특정 기본 파일은 없고, 자동 로딩은 정렬된 첫 경로를 사용한다. 필요한 폴더가 비면 다른 모델군으로 대체하지 않고 설치 필요 오류를 반환한다. `folder://`는 내부 workflow loader의 경로 선택자이며 사용자 프롬프트는 해석하지 않는다.

| 용도 | 모델 폴더 (ComfyUI models 기준) |
| --- | --- |
| Anima | diffusion_models/Anima, loras/Anima, text_encoders/Anima, vae/Anima |
| Illustrious | checkpoints/Illustrious, loras/Illustrious |
| MOSS | diffusion_models/MOSS, loras/MOSS, text_encoders/MOSS, vae/MOSS |
| Qwen | diffusion_models/Qwen, text_encoders/Qwen/Encoder, vae/Qwen |
| MiniMax H3 | diffusion_models/MiniMaxH3, loras/MiniMax, text_encoders/MiniMaxH3, vae/MiniMaxH3/Video, vae/MiniMaxH3/Audio |
| H3 보조 모델 | pdd_acc/MiniMaxH3/Ref2VA, pdd_acc/MiniMaxH3/FL2VA, latent_upscale_models/MiniMaxH3 |
| YuE2 음악 | checkpoints/YuE2 |
| TripoSplat 3D | diffusion_models/TripoSplat, clip_vision/TripoSplat, vae/TripoSplat/Image, vae/TripoSplat/Splat, background_removal/TripoSplat |

## 동작·오류 기록

큐 조회 복구, WebSocket 파싱, 이미지 SSE 오류를 원문 유틸로 기록한다. execution_error와 history 실패는 원격 예외 종류·문구·traceback을 포함한다. SSE 시작 이후 예외도 audit_stream으로 보존한다.

## API 레이턴시 기록

각 HTTP JSON/바이트/이미지 업로드 및 vLLM 요청에 timed_urlopen을 적용한다. WebSocket은 핸드셰이크·첫 메시지·전체 연결 시간을 따로 기록한다.
