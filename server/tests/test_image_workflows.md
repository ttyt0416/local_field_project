# 이미지 workflow 회귀 검사

Anima·Illustrious의 기존 loader·LoRA·I2I·prefix·source ownership 계약과 Qwen의 참조 이미지 처리를 검사한다. 제거한 Krea2 신규 요청, source 없는 편집 요청, 잘못된 편집 크기와 denoise를 거부하는지도 확인한다.

다중 참조의 두 모델 간 슬롯 순서, 혼합된 file_id·file_index, 업로드 index 누락·중복과 Anima 추가 참조 거부를 검사한다.

편집 family 공통 검증은 모델별 스텝·스케줄을 사용해 Qwen Turbo의 샘플링 계약을 유지한다.


Illustrious 체크포인트 미설치 상태에서도 옵션 조회가 성공하고, 설치된 LoRA·샘플러 목록은 유지하며 없는 체크포인트로 생성하면 422가 발생하는 회귀 검증을 포함한다.

Anima·Illustrious I2I에서 개선 활성 시 Prefix+개선 본문을 사용하면서 denoise를 유지하고, 끄면 Prefix+원문으로 돌아가는지 검증한다.
