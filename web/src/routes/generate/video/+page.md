# MiniMax H3 동영상 생성 화면

I2V·FL2V·R2V를 tab으로 선택한다. 각 input은 device storage 또는 stored content selection modal에서 선택한다. existing file은 `file_id`로 전송해 owner check 뒤 재사용하고 local file은 generation submit 때만 multipart로 전송한다.

동영상 생성의 stored content `생성` tab에서 image reference를 선택할 때는 `T2I (Anima)`, `I2I (Anima)`, `T2I (Illustrious)`, `I2I (Illustrious)` 4-category grid를 표시한다. selected category는 `/uploads`의 `generation_mode`와 `model_family` exact filter로 전송한다. video/audio reference는 image generation category filter 없이 기존 목록을 유지한다.

R2V source card마다 original media dimensions와 해당 source 전용 `이 사이즈 사용` action을 표시한다. action은 MiniMax H3의 1344 maximum과 32 multiple constraint에 맞춘 dimensions만 current video form에 적용한다.
