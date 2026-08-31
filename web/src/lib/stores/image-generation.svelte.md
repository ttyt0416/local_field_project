# 이미지 재생성 전달 상태

`imageGenerationStore`는 이미지 상세에서 generation 화면으로 한 번만 전달하는 Svelte 5 in-memory state다. 긍정·부정 프롬프트, checkpoint, LoRA strength, sampler, 크기와 seed를 보존한다.

Anima·Illustrious와 T2I·I2I가 추가된 뒤에는 `model_family`, `generation_mode`, `source_file_id`, `source_image_url`, `denoise`도 선택적으로 전달한다. 상세 화면은 mode에 맞는 route와 family query로 이동하고 destination은 state를 한 번 소비한다. 브라우저 영구 저장소에는 generation 설정을 남기지 않는다.
