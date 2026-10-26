# FL2V workflow

요청에서 선택한 `MiniMaxH3/` UNET을 사용하는 독립 ComfyUI API-format FL2V workflow다. built-in LoRA는 없고 server가 request에서 선택한 `MiniMax/` LoRA만 UNET 뒤에 ordered model-only chain으로 주입한다. 선택하지 않으면 guider와 scheduler가 UNET을 직접 사용한다. sampler는 `res_multistep`, scheduler는 `simple`, steps 기본값은 4이며 사용자 steps를 그대로 적용한다. 첫 프레임과 마지막 프레임을 각각 `LoadImage`로 받아 `MiniMaxH3ImageToVideo`의 optional frame 입력에 연결한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체다.

`0`은 direct `easy cleanGpuUsed` start output node다. request마다 `is_changed`가 갱신되어 fixed seed 재실행에서도 model loader 전에 cleanup을 실행한다.

UNET은 실행 시 선택 경로로 교체하며 인코더와 video/audio VAE는 역할별 folder:// 선택자를 live ComfyUI 목록으로 해석한다.
