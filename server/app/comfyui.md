# ComfyUI 이미지 저장

이미지 생성 요청은 ComfyUI `/prompt` 제출과 `image_generations` active row 생성 후 `202`를 반환한다. 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업의 ComfyUI history를 확인한다. 완료되면 첫 번째 결과 이미지를 독립 Storage API에 업로드하고 반환된 파일 ID를 `image_generations.storage_file_id`에 저장한다. 생성 row는 사용자 원문 `prompt`를 보존하고, 개선 prompt를 실제 사용한 경우 nullable `improved_prompt`에도 별도 저장한다. 생성 row의 `created_at`, `completed_at`, `elapsed_seconds`를 함께 저장하며, 프런트는 `/generation/image/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트와 timing 값을 받는다. 화면을 떠나도 서버 처리는 계속된다.

Storage가 설정된 생성 결과는 만료 읽기 URL을 사용한다. 기존 생성 데이터나 Storage 설정이 없는 환경은 기존 Local Field 이미지 프록시를 사용해 개발 환경과 기존 데이터를 유지한다. 이미지 조회 endpoint도 Storage 파일 ID가 있으면 서명 URL로 임시 리다이렉트한다.

Image·video·3D cancel endpoint는 shared ComfyUI의 `POST /api/jobs/{prompt_id}/cancel`을 호출한다. pending job은 ComfyUI queue에서 제거되고, running job은 해당 prompt만 interrupt한다. unknown 또는 terminal ID는 no-op이며 DB, SSE, 전역 job store는 `cancelled` terminal 상태를 사용해 polling과 대기 promise를 종료한다.

Video와 3D API workflow는 VRAM cleanup node를 포함하지 않는다. VRAM cleanup은 ComfyUI의 `LocalField VRAM Cleanup` custom output node를 graph에 직접 추가하고 Queue Prompt로 수동 실행한다. 이 node는 ComfyUI model unload, CUDA cache, IPC cache를 shared process에서 비운다.

lora strength는 기본값 `1.0`이고 별도 최대·최소 범위를 적용하지 않는다. 생성 seed는 PostgreSQL `BIGINT`에 저장 가능한 signed 64-bit 범위로 제한한다. 공통 Comfy model option reader는 legacy list schema와 ComfyUI V3 `COMBO` `{ options: [...] }` schema를 모두 처리한다.

공통 Comfy progress state는 현재 실행 node ID도 보존한다. image/video caller는 기존 progress 계약을 그대로 사용하고, TRELLIS.2 router는 node ID를 background cleanup·structure·shape·texture·mesh stage로 매핑한다.

`GET /generation/image/options?family=anima|moss|minimax_h3_image`는 family별 설치 모델과 기본 설정을 반환한다. Anima는 `diffusion_models/Anima/` split model과 `vae/Anima/`를 사용한다. Krea2는 신규 생성과 모델 선택에서 제거했다. 이전 Krea2 생성 기록과 프리셋 데이터는 보존한다. T2I는 Anima·MOSS·MiniMax H3-Image를 지원하며 negative prompt 기본값은 빈 문자열이다. prefix는 conditioning에서만 본문 앞에 합성하고 DB에는 별도로 보관한다. Anima·MOSS prompt enhancement는 Danbooru tags와 자연어를 사용한다. Anima I2I도 T2I와 같은 LLM 개선 API를 사용한다.

`POST /generation/image/i2i`는 multipart payload와 소스 이미지 한 개를 받는다. local file은 submit 시에만 Storage·media_assets에 저장하고 기존 file ID는 ownership을 확인해 재사용한다. Anima는 `LoadImage → ImageScale → VAEEncode → KSampler`와 0~1 denoise를 유지한다.



Structured LLM response가 `finish_reason=length`로 끝나면 server는 raw output and user prompt 없이 response schema name, configured token cap, completion token count, raw character count, JSON completion, trailing whitespace count, last schema field, parsed shot count를 warning log 한 줄로 남긴다. `_LLMError`는 decoded provider response를 caller에 전달하며 VIDEO prompt route는 이를 Error DB에 저장한다.



## MOSS

MOSS는 T2I 전용이며 `diffusion_models/MOSS/` 아래의 체크포인트를 파일명과 관계없이 인식한다. 중첩 하위폴더를 포함한다. `text_encoders/MOSS/`의 인코더(type `moss_image`)와 `vae/MOSS/`의 VAE를 사용한다. 기본값은 Euler·SGM Uniform, 50 steps, CFG 3, shift 5이다. EmptyFlux2LatentImage에서 생성하며 i2i 요청·소스 이미지·참조 입력은 거부한다. 외부 참조 패처는 워크플로와 모델 옵션에 연결하지 않는다. 레이아웃은 선택된 원문 또는 LLM 개선 프롬프트를 중앙 기준 JSON으로 변환하며 박스·표시할 텍스트는 그대로 보존한다. 가로·세로는 범위·배수 검사 없이 전달한다. DMD 버튼은 SFT에 최신 DMD LoRA 0.7, 8 steps, CFG 1을 선택한다.

참조 패처 출처는 https://github.com/silveroxides/ComfyUI-UtilsCollection 이며 설치 revision은 `52524719f934c7cc09382e2560f27f6967636255`이다. 누락된 의존성 `unifiedefficientloader==0.5.4`를 ComfyUI 환경에 추가했다.

가중치 출처: https://huggingface.co/Comfy-Org/MOSS-Image 의 SFT BF16·INT8 텍스트 인코더·small VAE와 https://huggingface.co/lodestones/MOSS-Image-SFT-8-steps-dmd 의 lora_latest.safetensors를 사용한다. Base 본체와 폐기된 DMD 전용 transformer 파일은 받지 않는다.



모든 family에서 활성화 시 개선된 본문이 필수이며 I2I 소스 업로드 전에 검증한다. 비활성화 시 원문을 사용하고 Prefix는 선택된 본문 앞에 한 번만 붙인다. 활성 상태·원문·개선 본문은 생성 기록·프리셋·재생성에 따로 보존한다. options의 prompt_enhancer_available은 공통 개선 기능 지원을 뜻하며 LLM 실시간 건강 검사는 아니다. 요청 유효성 오류는 직렬화 가능한 context 제외 형식으로 반환한다.




MOSS LoRA는 `loras/MOSS/` 및 하위폴더에서 파일명과 관계없이 선택한다. 원본 Hugging Face 저장소 이름은 MOSS-Image-SFT-8-steps-dmd이며 로컬 분류 이름과 구분한다.

## 공통 모델 폴더 검색

체크포인트·LoRA 선택과 이미지·동영상·음악·3D 자동 모델 로딩은 ComfyUI의 live object_info에서 역할별 폴더 및 하위폴더를 검색한다. 파일명 allowlist나 특정 기본 파일은 없고, 자동 로딩은 정렬된 첫 경로를 사용한다. 필요한 폴더가 비면 다른 모델군으로 대체하지 않고 설치 필요 오류를 반환한다. `folder://`는 내부 workflow loader의 경로 선택자이며 사용자 프롬프트는 해석하지 않는다.

| 용도 | 모델 폴더 (ComfyUI models 기준) |
| --- | --- |
| Anima | diffusion_models/Anima, loras/Anima, text_encoders/Anima, vae/Anima |
| MOSS | diffusion_models/MOSS, loras/MOSS, text_encoders/MOSS, vae/MOSS |
| MiniMax H3 | diffusion_models/MiniMaxH3, loras/MiniMax, text_encoders/MiniMaxH3, vae/MiniMaxH3/Video, vae/MiniMaxH3/Audio |
| H3 보조 모델 | pdd_acc/MiniMaxH3/Ref2VA, pdd_acc/MiniMaxH3/FL2VA, latent_upscale_models/MiniMaxH3 |
| YuE2 음악 | checkpoints/YuE2 |
| TripoSplat 3D | diffusion_models/TripoSplat, clip_vision/TripoSplat, vae/TripoSplat/Image, vae/TripoSplat/Splat, background_removal/TripoSplat |

## 동작·오류 기록

큐 조회 복구, WebSocket 파싱, 이미지 SSE 오류를 원문 유틸로 기록한다. execution_error와 history 실패는 원격 예외 종류·문구·traceback을 포함한다. SSE 시작 이후 예외도 audit_stream으로 보존한다.

## API 레이턴시 기록

각 HTTP JSON/바이트/이미지 업로드 및 LLM 요청에 timed_urlopen을 적용한다. WebSocket은 핸드셰이크·첫 메시지·전체 연결 시간을 따로 기록한다.


## 공용 사용

Local Field 계정 인증과 사용자별 소유자 인자를 제거하고 콘텐츠·작업을 공용으로 처리한다. 외부 서비스의 API 토큰과 기존 오류 기록은 유지한다.

## 이미지 표시 진단

ComfyUI 완료 확인 후 결과 다운로드·스토리지 업로드·DB 갱신·읽기 URL 준비를 image.finalize TRACE로 묶는다. 기존 외부 호출 시간에 prompt_id와 부모 request_id가 연결되어 /view, Storage POST /files, URL 발급을 구분할 수 있다. 완료 SSE 직렬화 시 image.result_delivery에 prompt_id·image_count를 기록한다. 이 시각은 직렬화 시점이며 브라우저 도착은 프런트 generation_result_received 로그로 확인한다. 생성·저장·실패 처리 동작은 유지한다.

`image.persist`는 완료 데이터의 DB 갱신 시간만 prompt_id·file_id와 함께 기록해 스토리지 전송과 구분한다.

## 프롬프트 강화 출력 문자

기본 구조화 출력은 문장 마침표와 Danbooru 태그의 밑줄·괄호를 허용한다. 마침표가 차단되어 Gemma가 문장을 계속 이어 쓰거나 태그 이름을 표현하지 못하는 문제를 방지하며, 기존 비어 있는 응답·허용 문자·JSON·출력 길이 검증을 유지한다.



## vLLM 생성 모델 전환

공통 생성 클라이언트는 schema를 `structured_outputs.json`, 명시적 영상 GBNF를 `structured_outputs.grammar`로 전송한다. 실제 schema의 패턴·길이는 생략하지 않으며 모델에 보여주는 구조 힌트만 간결하게 유지한다. `enable_thinking=false`, `reasoning_effort=none`, 길이 중단·JSON 파싱·provider_response 감사 기록을 유지한다.

선택적 image_inputs의 (label, data URL) 목록을 같은 user message의 text·image_url parts로 묶는다. 일반 이미지·음악 강화는 기존 문자열 메시지를 사용한다. 영상 강화만 실제 참조 이미지의 label을 붙여 전달한다.

서빙 backend는 LLGuidance 기반 guidance로 명시 고정한다. auto 또는 XGrammar로 자동 선택하지 않는다.

연결 실패 안내도 vLLM 생성 서버 명칭을 사용한다.

MiniMax H3-Image는 minimax_h3_image family로 T2I·I2I를 제공한다. diffusion_models/MiniMaxH3Image와 vae/MiniMaxH3Image를 사용하며 text_encoders/MiniMaxH3의 기존 Qwen3-VL NVFP4 인코더를 공유한다. MiniMaxH3ImageConditioning을 사용하는 ComfyUI 0.45.0 이상이 필요하다. Euler·Simple·6 steps·CFG 1·Denoise 1을 사용하고 기본 크기는 2048×2048이다. 부정 지시는 긍정 프롬프트에 작성한다. I2I는 소스와 추가 참조 15장까지 순서대로 Picture 1~16에 연결하고 기존 reference_images 열·Storage 참조 검사로 보존한다. 프롬프트 개선은 공통 vLLM에서 자연어만 반환하며 별도 PE 가중치를 설치하지 않는다.

가중치 출처: https://huggingface.co/Comfy-Org/MiniMax-H3-Image revision 0bb149f51e3156ed4b90dd45d5620346bfe1df8f.
- minimax_h3_image_pruned_int8_convrot.safetensors: 20,979,314,802 bytes, SHA-256 83eb140f1ff95c068f8a6886e6d3f3d0d4ab2e07bb2fe6d2ef992a51146ee622.
- minimax_h3_image_vae_fp16.safetensors: 1,168,505,312 bytes, SHA-256 d80e9c2e5cfc9844869961ff5a58c9a9e52182df6bfb30b26018dd7f348721af.
- 기존 공유 인코더 qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors: SHA-256 35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6. 공식 저장소 파일과 동일함을 검증하고 재사용한다.

H3-Image 개선 본문에는 공통 Danbooru용 ASCII 문자 제한을 적용하지 않는다. `<Picture N>` 참조 표식과 사용자가 요청한 비영어 화면 문구를 구조화 응답에서도 그대로 표현할 수 있다. JSON·빈 응답·길이 검증은 공통 경로를 유지한다.

T2I·I2I의 width·height는 정수형만 유지하고 최소·최대·배수 검사를 적용하지 않는다. 모든 이미지 family의 workflow는 공통 단계에서 원본 크기를 네이티브 PrimitiveInt 출력으로 연결해 ComfyUI 입력 위젯의 크기 범위 검사에도 걸리지 않도록 한다. 실제 latent 구성과 출력 크기 처리는 각 네이티브 모델 노드가 수행한다.
