# 이미지 프롬프트 개선 검증

Anima·MOSS는 같은 vLLM 자연어+Danbooru 태그 경로와 temperature 0.6을 사용하고 Illustrious는 검증된 태그만 반환하는지 확인한다. Qwen은 이미지 편집용 시스템 지시와 자연어 전용 structured output을 사용하며 태그 검색을 호출하지 않는다. 한국어·문장부호·줄바꿈이 공통 vLLM JSON 응답 파싱을 통과하는지 검증한다. 기존 기본 문자 패턴, 공유 vLLM 모델과 길이 제한 진단 계약도 유지한다.

공통 helper의 labeled image parts가 Picture label 바로 다음에 전달되고 기존 text-only 호출의 message 형태는 유지하는지 확인한다.
