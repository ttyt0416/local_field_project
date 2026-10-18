# 이미지 workflow 회귀 검사

Anima·Illustrious의 기존 loader·LoRA·I2I·prefix·source ownership 계약과 FLUX 3 Klein의 image-aware prompt upsampling·reference conditioning·matching empty latent·기본 sampler 설정을 검사한다. 제거한 Krea2 신규 요청, source 없는 편집 요청, 잘못된 편집 크기와 denoise를 거부하는지도 확인한다.

다중 참조의 두 모델 간 슬롯 순서, 혼합된 file_id·file_index, 업로드 index 누락·중복과 Anima 추가 참조 거부를 검사한다.

편집 family 공통 검증은 모델별 스텝·스케줄을 사용해 Qwen Turbo의 고정 샘플링과 기존 FLUX 검증을 함께 유지한다.
