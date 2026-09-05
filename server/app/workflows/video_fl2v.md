# FL2V workflow

Dasiwa MiniMax H3 int8 `DasiwaMinimaxH3_dasiwaHybridV1_int8` UNET을 사용하는 독립 ComfyUI API-format FL2V workflow다. built-in LoRA는 없고 server가 request에서 선택한 `MiniMax/` LoRA만 UNET 뒤에 ordered model-only chain으로 주입한다. 선택하지 않으면 guider와 scheduler가 UNET을 직접 사용한다. sampler는 `res_multistep`, scheduler는 `simple`, steps는 4이며 Eros 선택 시 server가 steps만 6으로 patch한다. 첫 프레임과 마지막 프레임을 각각 `LoadImage`로 받아 `MiniMaxH3ImageToVideo`의 optional frame 입력에 연결한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체다.
