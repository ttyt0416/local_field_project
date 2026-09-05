# R2V workflow

Dasiwa MiniMax H3 int8 `DasiwaMinimaxH3_dasiwaHybridV1_int8` UNET에 `VBVR_H3_attn_only` 뒤 `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16` Turbo LoRA를 적용한 독립 ComfyUI API-format R2V workflow다. sampler는 `res_multistep`, scheduler는 `simple`, steps는 4이다. Eros 선택 시 서버가 UNET과 LoRA chain을 Eros contract로 patch한다. 서버가 선택된 참조 이미지·동영상·오디오마다 `LoadImage`·`LoadVideo`·`LoadAudio` node를 추가한다. ComfyUI 0.34.2의 공통 `/upload/image` 입력 저장 route에 파일을 올린 뒤 해당 loader가 확장자에 맞게 읽는다. 동영상은 `GetVideoComponents`로 프레임과 paired audio를 분리한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체다.
