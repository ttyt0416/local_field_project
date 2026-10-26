# 이미지 재생성 전달 상태

`imageGenerationStore`는 이미지 상세에서 generation 화면으로 한 번만 전달하는 Svelte 5 in-memory state다. 긍정·부정 프롬프트, checkpoint, LoRA strength, sampler, 크기와 seed를 보존한다.

Anima·Illustrious와 T2I·I2I가 추가된 뒤에는 `model_family`, `generation_mode`, `source_file_id`, `source_image_url`, `denoise`도 선택적으로 전달한다. 상세 화면은 mode에 맞는 route와 family query로 이동하고 destination은 state를 한 번 소비한다. 브라우저 영구 저장소에는 generation 설정을 남기지 않는다.


재생성 파라미터의 reference_images는 추가 참조의 file_id·filename·url을 순서대로 전달한다. 소스 이미지와 구분하며 localStorage에는 저장하지 않는다.

## MOSS

MOSS 재생성은 moss 설정을 함께 전달한다. 화면에서 기본값과 저장된 영역을 복원해 레이아웃 및 r2i 프로필을 유지한다.

재생성 모델 family에 qwen_image_2_1을 허용하며 원본·참조 순서와 실행 파라미터를 I2I 페이지에 전달한다.

prompt_enhancement_enabled를 원본·다중 참조와 함께 재생성 파라미터로 전달한다.

improved_prompt를 선택 필드로 전달해 T2I·I2I 모두 개선 활성 상태와 본문을 함께 복원한다.
