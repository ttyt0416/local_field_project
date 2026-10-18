# 프리셋 회귀 검사

이미지 family·mode별 namespace와 사용자 ownership, 저장 필드·기본값 처리를 검사한다. FLUX 3 Klein의 `i2i_flux3_klein`을 독립 type으로 허용하며 기존 Krea2 데이터 타입을 보존한다.

요청 이름 정리·선택 필드 보존·지원하지 않는 값 거부와 video steps·use_pdd 저장도 검사한다. 사용자·타입별 기본 프리셋 중복 방지는 PostgreSQL partial unique index가 담당한다.

MOSS 레이아웃만 저장하는 프리셋, 빈 negative_prompt, Qwen LLM 강화의 true/false 저장을 검증한다.
