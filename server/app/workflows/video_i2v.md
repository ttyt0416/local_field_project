# I2V workflow

MiniMax H3 기반 10Eros `TURBO-hybrid_beta4_int8_convrot` UNET와 `VBVR_H3_attn_only` LoRA를 기본 적용한 ComfyUI API-format I2V workflow다. sampler는 `res_multistep`, scheduler는 `simple`, steps는 6이다. `LoadImage`의 입력 파일, 프롬프트, 크기, frame length, seed는 서버가 생성 요청 시 patch한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체로 저장한다.
