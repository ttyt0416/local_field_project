# H3 영상 프롬프트 GBNF

`video_prompt_gbnf`는 schema의 property order·required fields·array cardinality·scene IDs·integer range를 native GBNF로 컴파일한다. vLLM LLGuidance의 native GBNF 변환과 root 규칙을 사용한다.

한 번의 LLM 요청에서 모든 출력 내용에 같은 선택 언어 규칙을 적용한다. 한국어·영어·일본어 선택 목록의 문자 범위를 동적으로 합쳐 설명·대사·가사·화면 글자에 공통으로 사용한다. 인용문이나 원문에 선택하지 않은 언어가 있어도 예외로 허용하지 않으며 원문 literal 고정과 누락 검증은 사용하지 않는다.

audio의 `<d>[Language] ...</d>`와 text의 큰따옴표 내부도 같은 문자 범위로 제한한다. 대사 태그의 Language는 선택된 언어 이름만 허용한다. JSON Unicode escape로 비선택 문자를 우회할 수 없다. label은 실제 manifest의 Picture·Video·Audio만 허용하며 Subject 정의는 별도 서버 검증을 거친다. R2V summary 작업 유형과 보존 유형, 화자 ID 등 H3 구조 표식은 유지한다. voiceover 설명은 선택 언어로 작성한다.

GBNF의 반복 수는 marker를 하나의 atom으로 세므로 최종 decoded 문자 길이·앞뒤 공백·참조 정의·장면 시간 순서는 서버가 추가로 검증한다. `field_pattern`은 JSON decode 뒤 모든 내용에 동일한 언어 제한을 다시 검사한다. 문자 범위는 의미상 언어 판정이 아니며 일본어 한자는 다른 언어와 공유한다.

서빙 backend는 LLGuidance 기반 guidance로 명시 고정한다. auto 또는 XGrammar로 자동 선택하지 않는다.

대사 제어 태그는 <d>[Language] 본문 내부의 경계에만 둔다. 시작은 선택적 <scenetrans> 한 개, 끝은 선택적 <scenetrans> 또는 <cutoff> 한 개이며 그 사이에는 대사 문자가 필요하다. 태그를 독립 audio atom이나 대사 본문 반복 atom으로 허용하지 않아 연속 태그 생성 경로를 제거한다. field_pattern도 같은 배치를 검증한다.

각 필드는 선택 언어의 문자·숫자 또는 해당 필드의 정상 구조 표식으로 시작한다. 콜론 접두사나 문장부호만 있는 결과를 생성 문법과 서버 검증에서 막으며 text의 명시적인 인용 문자열은 보존한다.
