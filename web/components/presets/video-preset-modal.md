# VIDEO GEN 프리셋 모달

영상 생성 프리셋의 저장·수정 모달이다. 생성 화면 또는 Vault detail에서 현재 prompt, mode, checkpoint, LoRA name·strength, 크기, 길이, FPS, steps, PDD state, seed를 초기값으로 받아 저장한다. 선택한 필드만 `video` 타입으로 저장하고 기존 1344 product cap 없이 MiniMax H3 native 32~16384 range와 32 pixel step을 사용한다. checkpoint는 current mode의 folder-filtered modal에서 Eros와 Dasiwa를 표시하고 Dasiwa가 default다. LoRA field는 `MiniMax/` allowlist만 folder-filtered modal에서 multi-select하고 각 strength를 보존한다. load는 current mode options를 받은 뒤 checkpoint와 available LoRA를 적용한다. 공용 `Modal`의 `80dvh` 최대 높이와 내부 스크롤을 사용한다.
