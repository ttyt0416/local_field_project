# MiniMax H3 동영상 생성

`POST /generation/video/{mode}`는 `i2v`, `fl2v`, `r2v`를 각각 독립 workflow로 실행한다. R2V는 참조 이미지·동영상·오디오를 받으며, 동영상은 ComfyUI에서 프레임과 paired audio로 분리한다. 선택된 기존 Storage 파일은 소유권을 확인해 재사용하고, 새 이미지·동영상·오디오는 이 요청이 실제로 시작될 때만 Storage에 업로드한다. 선택만 하거나 미리보기만 하는 동작은 업로드·DB 생성·ComfyUI queue 제출을 수행하지 않는다.

요청은 직접 `width`와 `height`를 받지 않고 fixed `aspect_ratio`와 base `megapixels`를 받는다. `megapixels`는 `ROUND_HALF_UP`으로 한 자리로 정규화하며 0.1 MP 미만은 거부한다. normal path와 learned target path는 모두 width와 height가 32 pixel multiple인 MiniMax H3 patch grid를 고른다. optional `upscale_mode="learned_3d"`는 base보다 큰 `target_megapixels`를 반드시 받으며 target은 learned node의 같은 32 pixel alignment grid에서 별도로 계산한다. workflow는 base generation output을 `LTXVSeparateAVLatent`로 나눠 video latent만 `MinimaxH3LatentUpscaler3D` target dimensions path에 전달하고 original audio latent와 다시 concat한다. 이 path는 PDD refine 또는 PDD scheduler를 사용하지 않는다. runtime은 `Comfyui_Minimax_h3_latent_Upscaler` node commit `d7c01b9011f2e8439493f6c02c29995a27df276f`와 `latent_upscale_models/MiniMaxH3/`의 모델를 필요로 하며, artifact는 Hugging Face revision `13ccf95d85d120bdbc92c05b1247a6e147bf54bf`, SHA-256 `043e5a48e161610ef6c3ea974645220354d06fa618abca15f76d084812eb55c2`로 pin한다. Ref image/video의 원본 크기는 output geometry에 영향을 주지 않으며 conditioning input으로만 사용한다. `fps`는 1~120 범위의 영상 프레임 레이트이며 기본값은 24이다. 서버는 이를 `video_generations.fps`, workflow의 `CreateVideo.fps`, duration 기반 frame length에 함께 반영한다.

I2V·FL2V·R2V workflow는 `diffusion_models/MiniMaxH3/`에서 선택한 UNET을 사용한다. 특정 파일명이나 버전 제한은 없으며 기본값은 설치된 경로를 정렬한 첫 모델이다. MiniMax workflow에는 고정 LoRA가 없으며, 사용자가 선택한 `MiniMax/` LoRA만 UNET 뒤 selection order와 strength 그대로 연결한다. 기본 model chain은 `PathchSageAttentionKJ(auto, allow_compile=false)`·`SolAttnPatch(tau=1.2, 0.2~0.8, min_tokens=4096, exact_kv, Morton off)`·`EasyCache(reuse_threshold=0.3, 0.2~0.9)` 순서다. MiniMax H3 Morton reorder는 GPU allocator crash를 일으켜 off 상태로 두며, Sage·SolAttn conditioning sink·EasyCache는 그대로 사용한다. `use_pdd=true`면 checkpoint fingerprint와 일치하는 PDD Acc file을 적용하고 PDD가 반환한 sigma schedule과 Euler sampler를 사용하며 PDD upstream 제약에 따라 EasyCache는 넣지 않는다. video `steps`는 1~100의 persisted request 값이고 PDD는 4·6·8만 허용하며 값이 없을 때 PDD는 8, 일반 생성은 4를 사용한다. 파일명으로 steps를 변경하지 않는다. ComfyUI 입력 파일은 생성 요청 중에만 임시 입력으로 업로드한다. 생성 요청은 ComfyUI `/prompt` 제출과 DB active row 생성을 완료한 뒤 `202`를 반환한다. 이후 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업을 확인하고, ComfyUI history 완료 시 결과를 Storage에 저장하고 DB를 갱신한다. 프런트는 `GET /generation/video/{mode}/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트를 받으며, 화면을 떠나면 SSE 연결만 종료되고 서버 작업은 계속된다.

`GET /generation/video/options?mode=`는 current mode의 live ComfyUI `UNETLoader`에서 `MiniMaxH3/` 및 하위폴더의 모든 체크포인트를 반환한다. 폴더가 비면 빈 목록·기본값을 반환하고 실제 생성은 거부한다. `loras`는 live `LoraLoaderModelOnly`의 `MiniMax/` path만 반환하며, `samplers`와 `schedulers`는 각각 live `KSamplerSelect.sampler_name`과 `BasicScheduler.scheduler` choice를 반환한다. server는 checkpoint, LoRA, sampler, scheduler를 모두 live allowlist로 검증하고 normal workflow의 해당 node에 적용한다. `use_pdd=true`는 PDD upstream constraint에 따라 Euler sampler와 PDD sigma schedule을 강제하며 EasyCache를 넣지 않는다. requested `aspect_ratio`, normalized `megapixels`, sampler, scheduler와 calculated dimensions는 `video_generations`에 저장되어 long-video continuation, Vault detail, preset 저장에서 재현된다.

10초를 초과하는 요청은 서버가 정확히 최대 10초 길이의 sequence segment로 나눈다. 첫 segment만 사용자가 고른 I2V·FL2V·R2V workflow를 사용하고, 후속 segment의 실제 마지막 PNG frame 연결 방식은 request의 `continuation_mode`로 고른다. `r2v`는 final frame을 `<Picture 1>`로 prepend하고 prompt에서 다음 구간의 시작 frame으로 사용하도록 지시하며, 사용자가 고른 R2V image references는 `<Picture 2>`부터 같은 순서로 유지한다. long R2V는 final frame slot을 위해 사용자 image를 최대 8개로 제한한다. `i2v`는 same final frame을 I2V workflow `first_frame`으로 전달한다. public `prompt_id`와 SSE key는 sequence 전체에서 고정하고, DB의 `active_prompt_id`만 매 segment Comfy ID로 교체한다. worker가 claim/advance를 atomic하게 수행하므로 browser disconnect나 server restart가 이어지는 sequence를 끊지 않는다. intermediate segment는 internal Storage artifact이며 마지막 segment 완료 후 server-side concat 결과 한 개만 Vault output으로 남긴다.

`prompt`는 sequence 전체에 공통인 스타일·전체 배경이고, `input_segment_prompts`는 duration-derived segment 수와 정확히 일치하는 사용자 action 입력을 그대로 저장한다. 실행용 `segment_prompts`는 common context와 해당 구간 및 continuation instruction을 결합한 값이다. `improved_segment_prompts`는 사용자가 검토·수정한 vLLM proposal을 모든 구간에 대해 별도로 저장하고 Vault detail은 input 1 → improved 1 → input 2 → improved 2 순서로 표시한다. 사용자가 proposal을 검토·수정해 submit할 때만 enhanced prompt가 실행되고, vLLM은 원문 scene prompt를 자동 대체하지 않는다.

`VideoAsset`의 `file_id`는 기존 재사용 콘텐츠이고 `file_index`는 이번 multipart 요청의 새 파일이다. 새 파일과 기존 파일은 소유자 검증·형식 검증·크기 제한을 동일하게 적용한다.

`POST /generation/video/enhance-prompt`는 공통 스타일·배경과 현재 구간 지시를 vLLM으로 개선한다. 기존 JSON 요청에 optional `references` 목록을 추가했다. 각 참조는 kind, index, role, filename과 선택적인 image_data_url을 가진다. 이미지 미리보기는 최대 2MiB 문자열인 JPEG·PNG·WebP base64 data URL만 받고, 외부 URL이나 아직 생성되지 않은 continuation frame의 미리보기는 거부한다. image_url parts는 해당 Picture label과 함께 vLLM으로 전달한다. 영상·오디오는 역할·파일명만 전달하며 미디어를 실제로 확인했다고 주장하지 않도록 지시한다.

I2V와 FL2V는 shots와 두 sound field를, R2V는 추가로 subject_definitions·summary·retention_analysis를 strict JSON으로 받는다. shot은 start_ms·style·timeline·camera·audio·text를 유지한다. 각 text field 길이는 style 768, timeline 1536, camera 384, audio 2048, text 1024, sound field 각각 768자다. R2V의 정의·보존 관계는 각각 2048자, summary는 768자다. schema는 모든 Unicode 원문을 허용하고 앞뒤 공백·공백만인 field를 제한한다. 선택 언어는 설명문에 적용하며 대사·가사·이름·화면 문구는 원래 언어와 문장부호를 보존한다. 대사는 audio에서 `<d>[Language] ...</d>`와 일관된 화자 ID를 사용한다.

출력 budget은 기본 2048 tokens이며 명시적인 장면/샷 수, R2V의 추가 필드, 비영어 설명문, 긴 입력에 따라 늘어나고 최대 8192다. temperature 0.6과 120초 timeout을 유지한다. 샷 수의 schema 범위와 반환 순서에 대한 기존 정책은 유지하며 추가적인 의미 검증·재시도는 도입하지 않는다. 첫 샷도 timeline을 포함하고 시간 표기만 생략한다. shot의 exact N/A는 생략하고 top-level sound field의 N/A는 유지한다. I2V·FL2V는 알려진 첫·마지막 프레임을 시작 행에서 정렬하고, R2V는 6개 공식 section 중 detailed_description으로 shot을 조립한다. 완성된 형식의 개선문은 생성 단계에서 일반 참조 header를 다시 붙이지 않는다. 사용자 편집 freeform에는 기존 참조 header 동작을 유지한다. 결과 전체의 5000자 제한은 없고 편집한 결과를 그대로 제출한다. provider length·파싱 오류는 기존 provider_response audit을 유지한다.

`POST /generation/video/{mode}/{prompt_id}/cancel`은 ComfyUI `POST /api/jobs/{prompt_id}/cancel`을 호출한다. ComfyUI가 실행 중 작업은 interrupt하고 pending 작업은 해당 ID만 dequeue하며, Local Field가 queue snapshot을 따로 읽지 않는다.

`prompt_output_languages`는 ko·en·ja 중 한 개 이상을 받는다. 설명문 작성 언어를 선택하며 인용된 대사·가사·화면 글자·이름은 선택 언어와 관계없이 원문을 보존한다. 이를 위해 Unicode를 언어별 문자 정규식으로 차단하지 않는다.

세 video workflow의 `SaveVideo`는 ComfyUI V3 DynamicCombo API 형식에 맞춰 `format`과 `codec`을 평탄한 선택값으로 `/prompt`에 전달한다. ComfyUI가 이를 실행 시 내부 dynamic input object로 재구성하므로 중첩된 `format` object를 workflow에 넣지 않는다.

자동 인코더·video/audio VAE·PDD·업스케일 모델은 comfyui.md의 역할 폴더에서 검색한다. PDD 파일명·체크포인트 이름의 고정 매핑은 없으며 실제 모델 호환성은 PDD node의 fingerprint 검사로 확인한다. 업스케일 기록에는 실제 선택된 경로를 저장한다.

## 동작·오류 기록

영상 SSE, 원격 history 실패, 시퀀스 정리·후속 작업 취소 실패를 공통 유틸로 보존한다. 정상 heartbeat 타임아웃은 제외한다.

## API 레이턴시 기록

영상 입력 파일 업로드 요청에 공통 HTTP 시간 측정을 적용한다. 공유 ComfyUI 호출은 comfyui 유틸을 재사용한다.
