# 프리셋 API

`/presets`는 사용자별 `t2i`와 `video` 프리셋을 제공한다. 목록 조회와 삭제는 `type` query로 타입을 구분하고, 생성·수정 payload에도 타입을 포함한다. `t2i`는 `positive_prompt_prefix`, `negative_prompt_prefix`, 기존 이미지 생성 필드와 LoRA별 strength를 independent saved field로 보존한다. `video`는 prompt·mode(`i2v`, `fl2v`, `r2v`)·checkpoint·LoRA·비율·base MP·optional learned 3D upscale target MP·duration·fps·steps·`use_pdd`·seed를 저장한다. learned upscale preset은 `upscale_mode="learned_3d"`와 base보다 큰 target MP를 함께 저장하고 PDD를 허용하지 않는다. preset은 legacy product cap 없이 positive width·height를 보존하고, 실행할 때 image `16~16384 / 8 pixel multiple`, video `32~16384 / 32 pixel multiple` native contract를 적용한다. LoRA strength·개수와 video duration에는 고정된 최대·최소 범위를 적용하지 않으며, video steps는 1~100, 영상 fps 기본값은 24이고 허용 범위는 1~120이다. 저장 값이 없는 요청은 거부하며, 기존 사용자별 ownership과 타입별 기본 프리셋 정책을 유지한다.


## MOSS

MOSS는 T2I 전용 t2i_moss 네임스페이스를 사용한다. moss 값은 공통 MossSettings로 검증해 레이아웃을 저장하며 i2i_moss 요청은 거부한다.

Qwen 2.1 Turbo는 i2i_qwen_image_2_1 프리셋 네임스페이스를 사용한다. 실제 실행 시 8스텝·CFG 1·전용 스케줄을 검증한다.

빈 negative_prompt도 선택한 설정으로 저장해 MOSS의 기본 빈 부정 프롬프트 저장·초기화가 가능하다. Qwen LLM 강화 true/false 값은 exclude_none 처리에서 보존한다.
