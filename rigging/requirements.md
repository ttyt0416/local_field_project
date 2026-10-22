# 실행 의존성

추론은 Python 3.12와 GB10을 지원하는 기존 CUDA PyTorch를 읽기 전용으로 재사용하며 SkinTokens 전용 venv에 이 requirements를 설치한다. 검증 버전은 transformers 4.57.6·diffusers 0.36.0·PyTorch 2.14.0+cu130이다. GLB 전용 입출력을 사용하므로 bpy·Gradio·외부 Flash Attention 설치는 필요하지 않다.
