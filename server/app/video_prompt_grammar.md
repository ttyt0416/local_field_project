# H3 영상 프롬프트 GBNF

`video_prompt_gbnf`는 schema의 property order·required fields·array cardinality·scene IDs·integer range를 native GBNF로 컴파일한다. vLLM LLGuidance의 native GBNF 변환과 root 규칙을 사용한다.

설명문은 선택한 한국어·영어·일본어 문자 범위와 고정 protocol만 허용한다. 선택 언어 밖의 Unicode 원문은 audio의 `<d>[Language] ...</d>`와 text의 큰따옴표 안에서 허용한다. JSON Unicode escape로 설명문 제한을 우회할 수 없다. label은 실제 manifest의 Picture·Video·Audio만 허용하며 Subject 정의는 별도 서버 검증을 거친다. 인용 원문은 source_literals로 추출하여 JSON-encoded terminal로 고정한다. R2V summary의 작업 유형은 enum이다.

GBNF의 반복 수는 marker를 하나의 atom으로 세므로 최종 decoded 문자 길이·앞뒤 공백·원문 보존·참조 정의·장면 시간 순서는 서버가 추가로 검증한다. 문자 제약은 문장의 의미상 언어 판정이 아니다. `field_pattern`은 JSON을 decode한 뒤 같은 영역별 제약을 검사한다.

서빙 backend는 LLGuidance 기반 guidance로 명시 고정한다. auto 또는 XGrammar로 자동 선택하지 않는다.


설명 언어를 한국어·영어·일본어의 선택 집합으로 복구했다. GBNF와 decoded field_pattern은 같은 문자 범위를 사용하며 비선택 문자와 JSON Unicode escape 우회를 차단한다. 고정 protocol marker·N/A·보존 유형 enum·voiceover 문구는 예외로 허용한다. 대사·가사·화면 글자의 원문 terminal은 설명 언어와 독립적으로 보존한다. 일본어 한자는 다른 언어와 공유하므로 문자 범위 검증은 의미상 언어 판정이 아니다.
