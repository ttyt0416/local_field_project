# MiniMax H3 동영상 생성

`POST /generation/video/{mode}`는 `i2v`, `fl2v`, `r2v`를 각각 독립 workflow로 실행한다. R2V는 참조 이미지·동영상·오디오를 받으며, 동영상은 ComfyUI에서 프레임과 paired audio로 분리한다. 선택된 기존 Storage 파일은 소유권을 확인해 재사용하고, 새 이미지·동영상·오디오는 이 요청이 실제로 시작될 때만 Storage에 업로드한다. 선택만 하거나 미리보기만 하는 동작은 업로드·DB 생성·ComfyUI queue 제출을 수행하지 않는다.

요청의 `duration`은 고정된 최대·최소 범위 없이 영상 길이 초 단위로 받고, `fps`는 1~120 범위의 영상 프레임 레이트이며 기본값은 24이다. 서버는 이를 `video_generations.fps`, workflow의 `CreateVideo.fps`, duration 기반 frame length에 함께 반영한다.

I2V·FL2V·R2V 모두 10Eros `TURBO-hybrid_beta4_int8_convrot` UNET와 `VBVR_H3_attn_only` LoRA를 사용하며, `res_multistep` sampler와 `simple` scheduler에서 6 steps로 실행한다. 기존 mode별 Turbo LoRA files는 보존하지만 workflow는 참조하지 않는다. ComfyUI 입력 파일은 생성 요청 중에만 임시 입력으로 업로드한다. 생성 요청은 ComfyUI `/prompt` 제출과 DB active row 생성을 완료한 뒤 `202`를 반환한다. 이후 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업을 확인하고, ComfyUI history 완료 시 결과를 Storage에 저장하고 DB를 갱신한다. 프런트는 `GET /generation/video/{mode}/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트를 받으며, 화면을 떠나면 SSE 연결만 종료되고 서버 작업은 계속된다.

10초를 초과하는 요청은 서버가 정확히 최대 10초 길이의 sequence segment로 나눈다. 첫 segment만 사용자가 고른 I2V·FL2V·R2V workflow를 사용한다. 다음 segment는 반드시 R2V workflow이며 직전 실제 output video에서 `ffmpeg`로 추출한 마지막 PNG frame 하나를 `<Picture 1>` reference로 전달한다. public `prompt_id`와 SSE key는 sequence 전체에서 고정하고, DB의 `active_prompt_id`만 매 segment Comfy ID로 교체한다. worker가 claim/advance를 atomic하게 수행하므로 browser disconnect나 server restart가 이어지는 R2V 작업을 끊지 않는다. intermediate segment는 internal Storage artifact이며 마지막 segment 완료 후 server-side concat 결과 한 개만 Vault output으로 남긴다.

`prompt`는 sequence 전체에 공통인 스타일·전체 배경이고, `segment_prompts`는 duration-derived segment 수와 정확히 일치하는 시간 구간별 action 입력이다. segment 원문이 있을 때 서버는 공통 context와 해당 구간만 결합한다. `improved_segment_prompts`는 vLLM proposal이며 UI에서 구간 원문과 별도 textarea로 노출된다. 사용자가 proposal을 검토·수정해 submit할 때만 enhanced prompt가 실행되고, vLLM은 원문 scene prompt를 자동 대체하지 않는다.

`VideoAsset`의 `file_id`는 기존 재사용 콘텐츠이고 `file_index`는 이번 multipart 요청의 새 파일이다. 새 파일과 기존 파일은 소유자 검증·형식 검증·크기 제한을 동일하게 적용한다.

`POST /generation/video/enhance-prompt`는 이미지 생성과 같은 vLLM 기반 prompt 개선 endpoint다. 공통 스타일·배경 `prompt`와 현재 시간 구간의 `segment_prompt`를 분리해 받고, browser가 구간 순서대로 직렬 호출한다. vLLM은 이전 구간의 visual continuity만 이어가며 이전 timeline action을 반복하지 않아야 한다. vLLM은 `style`, `timeline`, `camera`, `audio`, `text`, `negative` 문자열 필드를 가진 JSON만 반환한다. 서버는 이 필드를 선택 언어의 6블록으로 순서대로 조립하며, Timeline은 선택한 duration 전체를 다루고 camera·audio·화면 text·negative 제약을 명시한다. 입력과 개선 결과의 reference marker는 `@imageN`, `[ImageN]` 계열을 `<Picture N>`, `<Video N>`, `<Audio N>`으로 정규화하고 실제 참조 입력 순서를 보존한다.

`prompt_output_languages`는 `ko`, `en`, `ja` 중 1개 이상을 받는 multi-select 필드다. 개선 결과는 선택 언어의 문자 집합 union과 숫자·ASCII 특수기호·공백·줄바꿈만 허용하는 JSON schema pattern과 서버 검증을 모두 통과해야 한다. 개선이 활성화된 생성 요청도 같은 6블록·문자 규칙을 다시 검증하며, 개선 결과가 없거나 규칙을 벗어나면 queue 제출과 입력 업로드 전에 `422`로 거절한다.

세 video workflow의 `SaveVideo`는 ComfyUI V3 DynamicCombo API 형식에 맞춰 `format`과 `codec`을 평탄한 선택값으로 `/prompt`에 전달한다. ComfyUI가 이를 실행 시 내부 dynamic input object로 재구성하므로 중첩된 `format` object를 workflow에 넣지 않는다.
