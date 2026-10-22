# SkinTokens GPU 추론

공식 저장소와 두 checkpoint를 그대로 사용한다. PyTorch SDPA를 별도 추론 process 안에서 flash_attn_interface 호환 함수와 Transformers from_config의 sdpa 설정에 연결한다. 기존 ComfyUI 패키지와 upstream 소스는 수정하지 않는다. --check는 의존성 import와 CUDA 가용성을 확인한다.

GLB의 Y-up을 공식 Blender parser와 같은 Z-up으로 변환하고 checkpoint의 predict_transform과 sampler를 적용한다. 공식 데모와 같은 articulation 클래스와 generation 기본값(top_k=5, top_p=.95, repetition_penalty=2, max_length=2048)을 사용한다. 예측한 sampled skin을 공식 Asset.from_data로 원본 vertex에 적용하고 전처리 affine의 역행렬로 joint를 원본 GLB 좌표·크기로 되돌린다. 변환이 affine가 아니거나 입력이 평면으로 퇴화하면 실패한다. 단계별 LOCAL_FIELD_STAGE 출력은 worker가 읽는다.
