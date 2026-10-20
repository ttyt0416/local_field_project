# ComfyUI 이미지 저장

이미지 생성 요청은 ComfyUI `/prompt` 제출과 `image_generations` active row 생성 후 `202`를 반환한다. 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업의 ComfyUI history를 확인한다. 완료되면 첫 번째 결과 이미지를 독립 Storage API에 업로드하고 반환된 파일 ID를 `image_generations.storage_file_id`에 저장한다. 생성 row는 사용자 원문 `prompt`를 보존하고, 개선 prompt를 실제 사용한 경우 nullable `improved_prompt`에도 별도 저장한다. 생성 row의 `created_at`, `completed_at`, `elapsed_seconds`를 함께 저장하며, 프런트는 `/generation/image/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트와 timing 값을 받는다. 화면을 떠나도 서버 처리는 계속된다.

Storage가 설정된 생성 결과는 만료 읽기 URL을 사용한다. 기존 생성 데이터나 Storage 설정이 없는 환경은 기존 Local Field 이미지 프록시를 사용해 개발 환경과 기존 데이터를 유지한다. 이미지 조회 endpoint도 Storage 파일 ID가 있으면 서명 URL로 임시 리다이렉트한다.

Image·video·3D cancel endpoint는 shared ComfyUI의 `POST /api/jobs/{prompt_id}/cancel`을 호출한다. pending job은 ComfyUI queue에서 제거되고, running job은 해당 prompt만 interrupt한다. unknown 또는 terminal ID는 no-op이며 DB, SSE, 전역 job store는 `cancelled` terminal 상태를 사용해 polling과 대기 promise를 종료한다.

Video와 3D API workflow는 VRAM cleanup node를 포함하지 않는다. VRAM cleanup은 ComfyUI의 `LocalField VRAM Cleanup` custom output node를 graph에 직접 추가하고 Queue Prompt로 수동 실행한다. 이 node는 ComfyUI model unload, CUDA cache, IPC cache를 shared process에서 비운다.

lora strength는 기본값 `1.0`이고 별도 최대·최소 범위를 적용하지 않는다. 생성 seed는 PostgreSQL `BIGINT`에 저장 가능한 signed 64-bit 범위로 제한한다. 공통 Comfy model option reader는 legacy list schema와 ComfyUI V3 `COMBO` `{ options: [...] }` schema를 모두 처리한다.

공통 Comfy progress state는 현재 실행 node ID도 보존한다. image/video caller는 기존 progress 계약을 그대로 사용하고, TRELLIS.2 router는 node ID를 background cleanup·structure·shape·texture·mesh stage로 매핑한다.

`GET /generation/image/options?family=anima|illustrious|flux3_klein|moss`는 family별 설치 모델과 기본 설정을 반환한다. Anima는 `diffusion_models/Anima` split model과 `qwen_image_vae.safetensors`를 사용하고 Illustrious는 full checkpoint를 사용한다. Krea2는 신규 생성과 모델 선택에서 제거했다. 이전 Krea2 생성 기록과 프리셋 데이터는 보존한다. T2I는 Anima·Illustrious·MOSS SFT를 지원하며 negative prompt 기본값은 빈 문자열이다. prefix는 conditioning에서만 본문 앞에 합성하고 DB에는 별도로 보관한다. Anima prompt enhancement는 Danbooru tags와 자연어를, Illustrious는 검증된 tags만 사용한다.

`POST /generation/image/i2i`는 multipart payload와 소스 이미지 한 개를 받는다. local file은 submit 시에만 Storage·media_assets에 저장하고 기존 file ID는 ownership을 확인해 재사용한다. Anima·Illustrious는 `LoadImage → ImageScale → VAEEncode → KSampler`와 0~1 denoise를 유지한다.

FLUX 3 Klein은 `flux3-image-klein-int8-convrot.safetensors`, `qwen3vl_4b_int8_convrot.safetensors` type `flux3`, 공식 FLUX.2 VAE를 별도 이름으로 저장한 `flux3-klein-vae.safetensors`를 사용한다. `qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors`와 공식 edit system prompt로 원본을 보며 수정 지시를 확장한 뒤, `ReferenceMultiLatent`의 positive·negative·empty latent를 sampler에 함께 연결한다. CFG와 denoise는 1, 기본 steps는 16, sampler와 scheduler는 Euler·Simple이다. 모델·인코더·VAE·필수 노드를 live object_info로 검사하며 다른 family의 checkpoint와 LoRA는 허용하지 않는다. 소스 없는 FLUX T2I 요청은 거부한다.

FLUX 편집 크기는 32~16384의 32 pixel multiple이며 source와 output latent 크기를 일치시킨다. 기존 Anima·Illustrious는 16~16384의 8 pixel multiple이다. Qwen Image 2.1은 사용자 요청으로 취소해 코드와 다운로드 파일에서 제거했다.

Structured vLLM response가 `finish_reason=length`로 끝나면 server는 raw output and user prompt 없이 response schema name, configured token cap, completion token count, raw character count, JSON completion, trailing whitespace count, last schema field, parsed shot count를 warning log 한 줄로 남긴다. `_VLLMError`는 decoded provider response를 caller에 전달하며 VIDEO prompt route는 이를 Error DB에 저장한다.

FLUX references는 추가 이미지 0~9개를 받으며 source를 합쳐 최대 10개다. file_id와 multipart file_index를 섞어 쓰고 업로드 index의 누락·중복·미사용 파일을 submit 전에 거부한다. 기존 파일은 소유권을 확인한다. 추가 이미지는 약 1MP의 비율을 보존해 VAE에 전달하며, 프롬프트 확장용 배치는 정사각 패딩으로 전체 내용을 유지한다. source와 추가 참조는 양쪽 모델에 동일한 순서로 전달한다.

현재 FLUX 가중치·인코더·프롬프트 확장 모델·VAE는 사용자 요청으로 제거했다. 다중 참조 UI와 연결 코드는 유지하며, 모델 미설치 상태에서는 생성 옵션 API가 설치 필요 오류를 반환한다.

## MOSS SFT

MOSS SFT는 T2I 전용이며 `moss_image_sft_bf16.safetensors`, `qwen3.5_9b_int8_convrot.safetensors` type `moss_image`, `flux2-vae_small.safetensors`를 사용한다. 기본값은 Euler·SGM Uniform, 50 steps, CFG 3, shift 5이다. EmptyFlux2LatentImage에서 생성하며 i2i 요청·소스 이미지·참조 입력은 거부한다. 외부 참조 패처는 워크플로와 모델 옵션에 연결하지 않는다. 레이아웃은 장면 설명을 중앙 기준 JSON으로 변환하고 별도 프롬프트 개선을 적용하지 않는다. 출력 크기는 16 배수이다. DMD 버튼은 SFT에 최신 DMD LoRA 0.7, 8 steps, CFG 1을 선택한다.

참조 패처 출처는 https://github.com/silveroxides/ComfyUI-UtilsCollection 이며 설치 revision은 `52524719f934c7cc09382e2560f27f6967636255`이다. 누락된 의존성 `unifiedefficientloader==0.5.4`를 ComfyUI 환경에 추가했다.

가중치 출처: https://huggingface.co/Comfy-Org/MOSS-Image 의 SFT BF16·INT8 텍스트 인코더·small VAE와 https://huggingface.co/lodestones/MOSS-Image-SFT-8-steps-dmd 의 lora_latest.safetensors를 사용한다. Base 본체와 폐기된 DMD 전용 transformer 파일은 받지 않는다.

Qwen Image 2.1 Turbo는 qwen_image_2_1 family로 I2I·다중 참조 생성을 제공한다. 공식 BF16 Turbo 본체, qwen3vl_8b_int8_convrot 인코더(type qwen_image), 전용 Qwen 2.1 VAE를 사용한다. TextEncodeQwenImage21에 원본을 image_1, 추가 참조를 image_2~image_10 순으로 전달한다. 원본은 선택한 출력 크기로 맞추고 추가 참조는 비율을 유지해 약 1MP·32배수로 줄인다. resolution 0으로 인코더 latent와 출력 캔버스를 일치시킨다. QwenImage21Cache auto/default와 공식 ManualSigmas [1,.978453,.95418,.926626,.89508,.845148,.704534,.414568,0], Euler·CFG 1·8 steps·Denoise 1을 사용하며 다른 조합은 업로드 전에 거부한다. 일반 KSampler 스케줄러로 대체하지 않는다. LLM 프롬프트 강화는 아래 설정을 따른다.

출처: https://huggingface.co/Comfy-Org/Qwen-Image-2.1 / https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo / https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_turbo_image_edit.json . 모델 배포 revision은 a8342359c61979b06a8dafb1a47991fe1f30e994이다.

Qwen 기본 요청은 LLM 강화가 켜진다. qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors를 TextGenerate(type qwen_image)에 연결하고 공식 I2I 시스템 프롬프트, thinking=true, 최대 4096 tokens, temperature 1·top_k 20·top_p .95를 사용한다. 원본·추가 참조를 같은 순서로 1024 정사각형에 패딩해 배치 전달한다. 강화 출력이 TextEncodeQwenImage21의 prompt 입력으로 연결되며 끄면 원문을 사용한다. 준비 여부를 옵션으로 제공하고 누락 시 해당 실행만 차단한다. 별도 텍스트 전용 enhance-prompt API는 Qwen에서 거부하며 생성 그래프에서 이미지와 함께 처리한다. 강화 활성 여부는 생성 기록·프리셋·재생성에 보존한다. 요청 유효성 오류는 직렬화 가능한 context 제외 형식으로 반환한다.

LLM이 토큰 제한 등으로 빈 문자열을 반환하면 StringCompare/ComfySwitchNode가 원래 수정 지시를 유지한다. 추론 과정 텍스트를 이미지 프롬프트에 넣지 않는다.


Illustrious 체크포인트가 설치되지 않은 경우 옵션 API는 빈 checkpoints와 빈 default_checkpoint를 반환한다. 프리셋 조회·편집은 유지하고 실제 생성 요청은 기존 모델 검증에서 422로 차단한다. ComfyUI 연결 장애는 기존 오류로 처리한다.


MOSS DMD LoRA의 설치 경로는 MOSS/lora_latest.safetensors로 통합한다. 원본 Hugging Face 저장소 이름은 MOSS-Image-SFT-8-steps-dmd이며 로컬 분류 이름과 구분한다.
