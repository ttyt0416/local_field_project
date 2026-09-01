# FL2V workflow

MiniMax H3 기반 10Eros `TURBO-hybrid_beta4_int8_convrot` UNET와 `VBVR_H3_attn_only` LoRA를 기본 적용한 독립 ComfyUI API-format FL2V workflow다. sampler는 `res_multistep`, scheduler는 `simple`, steps는 6이다. 첫 프레임과 마지막 프레임을 각각 `LoadImage`로 받아 `MiniMaxH3ImageToVideo`의 optional frame 입력에 연결한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체다.
