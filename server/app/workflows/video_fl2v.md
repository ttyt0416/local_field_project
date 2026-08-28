# FL2V workflow

MiniMax H3 `fl2va` 기반의 독립 ComfyUI API-format FL2V workflow다. 첫 프레임과 마지막 프레임을 각각 `LoadImage`로 받아 `MiniMaxH3ImageToVideo`의 optional frame 입력에 연결한다. `SaveVideo.format`은 ComfyUI dynamic combo 계약에 맞는 MP4/H.264 객체다.
