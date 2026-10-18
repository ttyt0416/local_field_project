# Prompt enhancement tests

Image prompt enhancement의 Anima natural-language and tag calls, Illustrious tag call, Krea2 natural-language call이 모두 `temperature=0.6`을 사용하는지 검증한다. Structured output character pattern과 safe length-exhaustion telemetry contract도 검증한다.

제거된 Krea 프롬프트 강화 테스트를 Qwen 편집 경로 검증으로 대체한다. Qwen은 별도 vLLM 요청 대신 생성 그래프의 로컬 I2I 프롬프트 강화 모델을 사용한다.
