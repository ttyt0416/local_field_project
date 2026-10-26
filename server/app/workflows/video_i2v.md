# I2V workflow

요청에서 선택한 `MiniMaxH3/` UNET을 사용하는 ComfyUI API-format I2V workflow다. built-in LoRA는 없고 server가 request에서 선택한 `MiniMax/` LoRA만 UNET 뒤에 ordered model-only chain으로 주입한다. 선택하지 않으면 guider와 scheduler가 UNET을 직접 사용한다. sampler는 `res_multistep`, scheduler는 `simple`, steps 기본값은 4이며 사용자 steps를 그대로 적용한다. `LoadImage`의 입력 파일, 프롬프트, 크기, frame length, seed는 server가 생성 요청 시 patch한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체로 저장한다.

`0`은 direct `easy cleanGpuUsed` start output node다. request마다 `is_changed`가 갱신되어 fixed seed 재실행에서도 model loader 전에 cleanup을 실행한다.

UNET은 실행 시 선택 경로로 교체하며 인코더와 video/audio VAE는 역할별 folder:// 선택자를 live ComfyUI 목록으로 해석한다.
