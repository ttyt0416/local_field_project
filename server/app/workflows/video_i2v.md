# I2V workflow

Dasiwa MiniMax H3 int8 `DasiwaMinimaxH3_dasiwaHybridV1_int8` UNET을 사용하는 ComfyUI API-format I2V workflow다. built-in LoRA는 없고 server가 request에서 선택한 `MiniMax/` LoRA만 UNET 뒤에 ordered model-only chain으로 주입한다. 선택하지 않으면 guider와 scheduler가 UNET을 직접 사용한다. sampler는 `res_multistep`, scheduler는 `simple`, steps는 4이며 Eros 선택 시 server가 steps만 6으로 patch한다. `LoadImage`의 입력 파일, 프롬프트, 크기, frame length, seed는 server가 생성 요청 시 patch한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체로 저장한다.
