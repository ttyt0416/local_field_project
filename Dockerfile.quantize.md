Erebus-RP-Engine-26B-A4B의 기기 내 NVFP4 변환 전용 이미지다. 서빙 이미지와 분리하여 compressed-tensors 0.20.1·LLM Compressor 0.15.0의 model-free PTQ를 사용한다. ARM64 CUDA 13·Torch 2.14.0 기반 이미지는 고정 digest를 재사용한다. 실행 시 변환 스크립트와 원본·결과 모델 디렉터리를 mount한다. 다른 서비스와 서빙 컨테이너의 Python 패키지를 변경하지 않는다.

Torch·CUDA·NCCL은 기반 이미지의 검증된 조합을 유지하도록 변환 도구는 --no-deps로 설치하고 데이터셋 유틸만 별도로 설치한다. CUDA에서 작은 fused expert 입력의 실제 NVFP4 변환을 확인했으며, packed uint8·FP8 group scales·FP32 global scales와 BF16 제외 모듈 보존을 검증했다.
