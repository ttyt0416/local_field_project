# R2V workflow

MiniMax H3 `ref2va` 기반의 독립 ComfyUI API-format R2V workflow다. R2V 전용 Turbo LoRA를 적용하고, 서버가 선택된 reference 이미지·오디오마다 `LoadImage`·`LoadAudio` node와 autogrow 입력 link를 요청 시 추가한다. 결과는 `SaveVideo` MP4 출력으로 저장한다.
