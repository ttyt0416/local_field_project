# FL2V workflow

MiniMax H3 FL2VA `minimax_h3_fl2va_pruned_int8_convrot` UNET에 `VBVR_H3_attn_only` 뒤 `minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy` Turbo LoRA를 적용한 독립 ComfyUI API-format FL2V workflow다. sampler는 `res_multistep`, scheduler는 `simple`, steps는 4이다. 첫 프레임과 마지막 프레임을 각각 `LoadImage`로 받아 `MiniMaxH3ImageToVideo`의 optional frame 입력에 연결한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체다.
