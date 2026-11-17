# MiniMax H3 동영상 생성

`POST /generation/video/{mode}`는 `i2v`, `fl2v`, `r2v`를 각각 독립 workflow로 실행한다. R2V는 참조 이미지·동영상·오디오를 받으며, 동영상은 ComfyUI에서 프레임과 paired audio로 분리한다. 선택된 기존 Storage 파일은 소유권을 확인해 재사용하고, 새 이미지·동영상·오디오는 이 요청이 실제로 시작될 때만 Storage에 업로드한다. 선택만 하거나 미리보기만 하는 동작은 업로드·DB 생성·ComfyUI queue 제출을 수행하지 않는다.

요청은 직접 `width`와 `height`를 받지 않고 fixed `aspect_ratio`와 base `megapixels`를 받는다. `megapixels`는 `ROUND_HALF_UP`으로 한 자리로 정규화하며 0.1 MP 미만은 거부한다. normal path와 learned target path는 모두 width와 height가 32 pixel multiple인 MiniMax H3 patch grid를 고른다. optional `upscale_mode="learned_3d"`는 base보다 큰 `target_megapixels`를 반드시 받으며 target은 learned node의 같은 32 pixel alignment grid에서 별도로 계산한다. workflow는 base generation output을 `LTXVSeparateAVLatent`로 나눠 video latent만 `MinimaxH3LatentUpscaler3D` target dimensions path에 전달하고 original audio latent와 다시 concat한다. 이 path는 PDD refine 또는 PDD scheduler를 사용하지 않는다. runtime은 `Comfyui_Minimax_h3_latent_Upscaler` node commit `d7c01b9011f2e8439493f6c02c29995a27df276f`와 `latent_upscale_models/MiniMaxH3/`의 모델를 필요로 하며, artifact는 Hugging Face revision `13ccf95d85d120bdbc92c05b1247a6e147bf54bf`, SHA-256 `043e5a48e161610ef6c3ea974645220354d06fa618abca15f76d084812eb55c2`로 pin한다. Ref image/video의 원본 크기는 output geometry에 영향을 주지 않으며 conditioning input으로만 사용한다. `fps`는 1~120 범위의 영상 프레임 레이트이며 기본값은 24이다. 서버는 이를 `video_generations.fps`, workflow의 `CreateVideo.fps`, duration 기반 frame length에 함께 반영한다.

I2V·FL2V·R2V workflow는 `diffusion_models/MiniMaxH3/`에서 선택한 UNET을 사용한다. 특정 파일명이나 버전 제한은 없으며 기본값은 설치된 경로를 정렬한 첫 모델이다. MiniMax workflow에는 고정 LoRA가 없으며, 사용자가 선택한 `MiniMax/` LoRA만 UNET 뒤 selection order와 strength 그대로 연결한다. 기본 model chain은 `PathchSageAttentionKJ(auto, allow_compile=false)`·`SolAttnPatch(tau=1.2, 0.2~0.8, min_tokens=4096, exact_kv, Morton off)`·`EasyCache(reuse_threshold=0.3, 0.2~0.9)` 순서다. MiniMax H3 Morton reorder는 GPU allocator crash를 일으켜 off 상태로 두며, Sage·SolAttn conditioning sink·EasyCache는 그대로 사용한다. `use_pdd=true`면 checkpoint fingerprint와 일치하는 PDD Acc file을 적용하고 PDD가 반환한 sigma schedule과 Euler sampler를 사용하며 PDD upstream 제약에 따라 EasyCache는 넣지 않는다. video `steps`는 1~100의 persisted request 값이고 PDD는 4·6·8만 허용하며 값이 없을 때 PDD는 8, 일반 생성은 4를 사용한다. 파일명으로 steps를 변경하지 않는다. ComfyUI 입력 파일은 생성 요청 중에만 임시 입력으로 업로드한다. 생성 요청은 ComfyUI `/prompt` 제출과 DB active row 생성을 완료한 뒤 `202`를 반환한다. 이후 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업을 확인하고, ComfyUI history 완료 시 결과를 Storage에 저장하고 DB를 갱신한다. 프런트는 `GET /generation/video/{mode}/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트를 받으며, 화면을 떠나면 SSE 연결만 종료되고 서버 작업은 계속된다.

`GET /generation/video/options?mode=`는 current mode의 live ComfyUI `UNETLoader`에서 `MiniMaxH3/` 및 하위폴더의 모든 체크포인트를 반환한다. 폴더가 비면 빈 목록·기본값을 반환하고 실제 생성은 거부한다. `loras`는 live `LoraLoaderModelOnly`의 `MiniMax/` path만 반환하며, `samplers`와 `schedulers`는 각각 live `KSamplerSelect.sampler_name`과 `BasicScheduler.scheduler` choice를 반환한다. server는 checkpoint, LoRA, sampler, scheduler를 모두 live allowlist로 검증하고 normal workflow의 해당 node에 적용한다. `use_pdd=true`는 PDD upstream constraint에 따라 Euler sampler와 PDD sigma schedule을 강제하며 EasyCache를 넣지 않는다. requested `aspect_ratio`, normalized `megapixels`, sampler, scheduler와 calculated dimensions는 `video_generations`에 저장되어 long-video continuation, Vault detail, preset 저장에서 재현된다.

10초를 초과하는 요청은 서버가 정확히 최대 10초 길이의 sequence segment로 나눈다. 첫 segment만 사용자가 고른 I2V·FL2V·R2V workflow를 사용하고, 후속 segment의 실제 마지막 PNG frame 연결 방식은 request의 `continuation_mode`로 고른다. `r2v`는 final frame을 `<Picture 1>`로 prepend하고 prompt에서 다음 구간의 시작 frame으로 사용하도록 지시하며, 사용자가 고른 R2V image references는 `<Picture 2>`부터 같은 순서로 유지한다. long R2V는 final frame slot을 위해 사용자 image를 최대 8개로 제한한다. `i2v`는 same final frame을 I2V workflow `first_frame`으로 전달한다. public `prompt_id`와 SSE key는 sequence 전체에서 고정하고, DB의 `active_prompt_id`만 매 segment Comfy ID로 교체한다. worker가 claim/advance를 atomic하게 수행하므로 browser disconnect나 server restart가 이어지는 sequence를 끊지 않는다. intermediate segment는 internal Storage artifact이며 마지막 segment 완료 후 server-side concat 결과 한 개만 Vault output으로 남긴다.

`prompt`는 sequence 전체에 공통인 스타일·전체 배경이고, `input_segment_prompts`는 duration-derived segment 수와 정확히 일치하는 사용자 action 입력을 그대로 저장한다. 실행용 `segment_prompts`는 common context와 해당 구간 및 continuation instruction을 결합한 값이다. `improved_segment_prompts`는 사용자가 검토·수정한 LLM proposal을 모든 구간에 대해 별도로 저장하고 Vault detail은 input 1 → improved 1 → input 2 → improved 2 순서로 표시한다. 사용자가 proposal을 검토·수정해 submit할 때만 enhanced prompt가 실행되고, LLM은 원문 scene prompt를 자동 대체하지 않는다.

`VideoAsset`의 `file_id`는 기존 재사용 콘텐츠이고 `file_index`는 이번 multipart 요청의 새 파일이다. 새 파일과 기존 파일은 소유자 검증·형식 검증·크기 제한을 동일하게 적용한다.

`POST /generation/video/enhance-prompt`는 공통 스타일·배경과 현재 구간 지시를 LLM으로 개선한다. 기존 JSON 요청에 optional `references` 목록을 추가했다. 각 참조는 kind, index, role, filename과 선택적인 image_data_url을 가진다. 이미지 미리보기는 최대 2MiB 문자열인 JPEG·PNG·WebP base64 data URL만 받고, 외부 URL이나 아직 생성되지 않은 continuation frame의 미리보기는 거부한다. image_url parts는 해당 Picture label과 함께 LLM으로 전달한다. 영상·오디오는 역할·파일명만 전달하며 미디어를 실제로 확인했다고 주장하지 않도록 지시한다.

I2V와 FL2V는 shots와 두 sound field를, R2V는 추가로 subject_definitions·summary·retention_analysis를 strict JSON으로 받는다. shot은 start_ms·style·timeline·camera·audio·text를 유지한다. 필드 제한은 style 768, timeline 3072, camera 384, audio 4096, text 2048, sound field 각각 768, R2V 정의·보존 각각 3072, summary 1024자다.

모든 출력 내용은 사용자가 선택한 한국어·영어·일본어 집합으로 작성한다. 한 번의 LLM 요청에 선택 언어 문자 범위를 동적으로 합쳐 적용하며 설명·대사·가사·화면 글자에 같은 제한을 사용한다. 대사·가사는 audio의 `<d>[Language] ...</d>`, 화면 글자는 text의 큰따옴표 내부에 작성하며 선택하지 않은 언어는 번역한다. `video_prompt_grammar.py`가 native GBNF로 JSON 구조, 장면 수·ID, 정수 범위와 모든 내용의 선택 언어를 제한한다. `\uXXXX` JSON 이스케이프 우회와 원문 literal 예외를 허용하지 않는다. 문자 grammar가 의미상 언어까지 판정하지는 않는다. prompt_output_languages를 schema·GBNF·서버 재검증에 동일하게 적용한다.

실제 Picture·Video·Audio label만 사용하며 새 Subject label은 R2V 정의에서 만들고 재사용한다. R2V summary는 공식 작업 유형 대괄호로 시작하고 retention_analysis에는 화자 ID를 넣지 않는다. 화자 복합 ID, 입을 닫는 지시, 장면 전환·중단 태그는 유지하며 voiceover 설명도 선택 언어로 작성한다.
개선 요청은 optional `scenes` 배열로 현재 시간 구간의 장면을 순서대로 받는다. 각 항목은 공백일 수 없고 최대 360개, 본문 합계 5000자까지 허용한다. 배열이 있으면 serialized 문장의 내부 heading을 다시 세지 않으며, 기존 client의 배열 없는 요청은 줄 시작의 `[Scene N]`, `[Shot N]`, `장면 N:`, `샷 N:` 경계를 해석한다. 별도 장면이 없으면 기존 자동 샷 수 범위를 유지한다. 명시한 장면이 N개이면 strict schema의 shots minItems·maxItems를 모두 N으로 설정하고 각 shot에 원본 장면의 `scene_id`를 요구한다. 초당 한 샷 상한을 적용하지 않으므로 짧은 후속 구간도 여러 장면을 보존할 수 있다.

서버는 반환 개수가 N인지, scene_id가 정확히 1부터 N까지 입력 순서대로 있는지 검증한다. 모든 샷은 0ms부터 시작하고 이후 시작 시각이 중복 없이 증가하며 현재 구간 끝 이전이어야 한다. 잘못된 결과는 503 오류로 전달하고 반환된 구조화 객체를 기존 provider_response 오류 기록에 보존한다. 의미가 같은 문장인지까지 자동 판별하거나 실패한 결과를 조용히 재배열·분할하지 않는다. scene_id는 최종 개선문에 출력하지 않는다.

출력 budget은 기본 2048 tokens이며 명시적인 장면/샷 수, R2V의 추가 필드, 원문 언어, 긴 입력에 따라 늘어나고 최대 8192다. temperature 0.6과 120초 timeout을 유지한다. 첫 샷도 timeline을 포함하고 시간 표기만 생략한다. shot의 exact N/A는 생략하고 top-level sound field의 N/A는 유지한다. I2V·FL2V는 알려진 첫·마지막 프레임을 시작 행에서 정렬하고, R2V는 6개 공식 section 중 detailed_description으로 shot을 조립한다. 완성된 형식의 개선문은 생성 단계에서 일반 참조 header를 다시 붙이지 않는다. 사용자 편집 freeform에는 기존 참조 header 동작을 유지한다. 결과 전체의 5000자 제한은 없고 편집한 결과를 그대로 제출한다. provider length·파싱 오류는 기존 provider_response audit을 유지한다.

`POST /generation/video/{mode}/{prompt_id}/cancel`은 ComfyUI `POST /api/jobs/{prompt_id}/cancel`을 호출한다. ComfyUI가 실행 중 작업은 interrupt하고 pending 작업은 해당 ID만 dequeue하며, Local Field가 queue snapshot을 따로 읽지 않는다.

강화 요청은 fps(기본 24, 1~120)와 aspect_ratio도 받는다. `17*n+5` 정렬된 frame_count/fps를 실제 로컬 시간으로 사용한다. 예를 들어 5초·24fps는 124프레임, 약 5.166667초다. FL2V 시작 행은 공식 `How the reference pictures align with the target video — ...` 형식이며 실제 종료 시각을 소수 두 자리로 표시한다. 이 완성된 개선문은 생성 단계에서 참조 header를 다시 붙이지 않는다.

세 video workflow의 `SaveVideo`는 ComfyUI V3 DynamicCombo API 형식에 맞춰 `format`과 `codec`을 평탄한 선택값으로 `/prompt`에 전달한다. ComfyUI가 이를 실행 시 내부 dynamic input object로 재구성하므로 중첩된 `format` object를 workflow에 넣지 않는다.

자동 인코더·video/audio VAE·PDD·업스케일 모델은 comfyui.md의 역할 폴더에서 검색한다. PDD 파일명·체크포인트 이름의 고정 매핑은 없으며 실제 모델 호환성은 PDD node의 fingerprint 검사로 확인한다. 업스케일 기록에는 실제 선택된 경로를 저장한다.

## 동작·오류 기록

영상 SSE, 원격 history 실패, 시퀀스 정리·후속 작업 취소 실패를 공통 유틸로 보존한다. 정상 heartbeat 타임아웃은 제외한다.

## API 레이턴시 기록

영상 입력 파일 업로드 요청에 공통 HTTP 시간 측정을 적용한다. 공유 ComfyUI 호출은 comfyui 유틸을 재사용한다.

## 공용 사용

Local Field 계정 인증과 사용자별 소유자 인자를 제거하고 콘텐츠·작업을 공용으로 처리한다. 외부 서비스의 API 토큰과 기존 오류 기록은 유지한다.

## 생성 LLM과 이미지 분석

요청 모델은 기기 내 변환한 Erebus-RP-Engine-26B-A4B NVFP4A16이며 vLLM 공통 클라이언트를 사용한다. 원본 vision encoder 가중치 누락과 사용자의 텍스트 전용 선택에 따라 `LLM_VISION_ENABLED=false`로 이미지 전달을 끈다. 입력 설명과 참조 label만 사용하며 선택 이미지, 미래 continuation frame, 영상·오디오를 관찰했다고 주장하지 않는다. 비전 모델로 교체하면 해당 설정으로 labeled image preview 전달을 다시 활성화할 수 있다. source 이미지의 지시문은 장면 데이터로 취급한다.

GBNF와 동일한 decoded field pattern, Pydantic 길이, 장면 ID·시간·참조 label을 서버에서 재검증한다. 오류는 기존 감사 경로에 provider_response와 함께 기록한다.

서빙 backend는 LLGuidance 기반 guidance로 명시 고정한다. auto 또는 XGrammar로 자동 선택하지 않는다.


영상 강화는 prompt_output_languages를 모든 출력 내용의 언어로 일괄 적용한다. schema·native GBNF·서버 재검증에 같은 선택 언어를 전달하며 대사·가사·화면 글자에도 예외를 두지 않는다. 장면 구조·참조 label·공식 접두문 등 protocol은 유지한다.

영상 프롬프트 개선도 이미지·음악과 동일한 공통 repetition_penalty=1.1, frequency_penalty=0.1, presence_penalty=0.1을 적용한다. 대사 내부의 연속 제어 태그 반복을 막는 GBNF와 같은 서버 재검증 규칙을 사용한다. 프런트 응답은 기존 improved_prompt.contents 계약을 유지한다.
