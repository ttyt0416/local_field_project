# 프리셋 API

`/presets`는 공용 `t2i`와 `video` 프리셋을 제공한다. 목록 조회와 삭제는 `type` query로 타입을 구분하고, 생성·수정 payload에도 타입을 포함한다. `t2i`는 `positive_prompt_prefix`, `negative_prompt_prefix`, 기존 이미지 생성 필드와 LoRA별 strength를 independent saved field로 보존한다. `video`는 prompt·mode(`i2v`, `fl2v`, `r2v`)·checkpoint·LoRA·비율·base MP·optional learned 3D upscale target MP·duration·fps·steps·`use_pdd`·seed를 저장한다. learned upscale preset은 `upscale_mode="learned_3d"`와 base보다 큰 target MP를 함께 저장하고 PDD를 허용하지 않는다. preset은 width·height 정수 값을 최소·최대·배수 검사 없이 보존한다. 이미지 실행에도 별도 크기 제한을 적용하지 않는다. LoRA strength·개수와 video duration에는 고정된 최대·최소 범위를 적용하지 않으며, video steps는 1~100, 영상 fps 기본값은 24이고 허용 범위는 1~120이다. 저장 값이 없는 요청은 거부하며, 기존 공용 ownership과 타입별 기본 프리셋 정책을 유지한다.


## MOSS

MOSS는 T2I 전용 t2i_moss 네임스페이스를 사용한다. moss 값은 공통 MossSettings로 검증해 레이아웃을 저장하며 i2i_moss 요청은 거부한다.


빈 negative_prompt도 선택한 설정으로 저장해 MOSS의 기본 빈 부정 프롬프트 저장·초기화가 가능하다. 프롬프트 개선 true/false 값은 exclude_none 처리에서 보존한다.

## 공용 사용

Local Field 계정 인증과 사용자별 소유자 인자를 제거하고 콘텐츠·작업을 공용으로 처리한다. 외부 서비스의 API 토큰과 기존 오류 기록은 유지한다.


현재 이미지 생성 모델은 Anima·MOSS·MiniMax H3-Image이며 I2I는 Anima·MiniMax H3-Image를 사용한다.

MiniMax H3-Image 프리셋은 t2i_minimax_h3_image와 i2i_minimax_h3_image로 분리한다. 기존 공통 설정 저장 계약을 사용한다.
