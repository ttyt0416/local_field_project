# 모델 다운로드 검증


MOSS base model 변형 이름들이 공통 MOSS 폴더를 선택하고, MOSS checkpoint는 diffusion_model·MOSS LoRA는 lora로 분류되는지 기존 lookup 회귀 테스트에서 검증한다.

MOSS 기본 폴더는 정확한 MOSS 경로이며 이름이 비슷한 폴더나 중첩된 styles/MOSS로 대체하지 않는지 확인한다. Checkpoint·LoRA 다운로드 요청의 빈 subfolder는 각각 diffusion_models/MOSS·loras/MOSS를 사용하고, 선택한 MOSS 하위폴더는 유지한다. 기본 폴더가 없으면 enqueue하지 않고 422로 거부한다.

개인 토큰 저장소는 합성 개인 토큰을 반환하도록 모킹하여 파일·큐 검증이 운영 DB에 접근하지 않도록 한다. 서버 공용 토큰 설정은 사용하지 않는다.
