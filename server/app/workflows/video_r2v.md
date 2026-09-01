# R2V workflow

MiniMax H3 기반 10Eros `TURBO-hybrid_beta4_int8_convrot` UNET와 `VBVR_H3_attn_only` LoRA를 기본 적용한 독립 ComfyUI API-format R2V workflow다. sampler는 `res_multistep`, scheduler는 `simple`, steps는 6이다. 서버가 선택된 참조 이미지·동영상·오디오마다 `LoadImage`·`LoadVideo`·`LoadAudio` node를 추가한다. ComfyUI 0.34.2의 공통 `/upload/image` 입력 저장 route에 파일을 올린 뒤 해당 loader가 확장자에 맞게 읽는다. 동영상은 `GetVideoComponents`로 프레임과 paired audio를 분리해 autogrow 입력에 연결한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체다.
