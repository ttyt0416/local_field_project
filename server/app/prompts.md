# Prompt enhancement

Image prompt enhancement는 기존 structured output contract와 10분 제한을 유지한다. Video는 같은 helper에 optional labeled image_url parts를 전달한다. 기본 2048, 최대 8192 tokens의 동적 budget과 필드별 길이 제한은 video.md를 따른다. 모든 string은 Unicode를 허용하므로 영어 설명 속 한국어 대사·화면 문구를 그대로 유지할 수 있다.

Music prompt enhancement는 YuE2 Style·Lyrics에 맞춰 description과 lyrics를 target별 separate vLLM request로 처리한다. 최종 `{contents}`는 서버가 조립하며 `ko`, `en`, `ja` 중 selected output language를 1개 이상 사용한다. description target은 lyrics를 context로만 사용한다. lyrics target은 기존 lyrics가 있으면 section order, tag, line break를 유지하며 개선하고, 비어 있으면 description과 duration을 기준으로 새 가사를 생성한다. 둘 다 `temperature=0.6`, `max_tokens=4096`, `timeout_seconds=300`을 사용한다.

Video는 공통 사용자 의도·물리적 연속성·화자·원문 보존 규칙과 I2V·FL2V·R2V 전용 지시문을 결합한다. I2V는 첫 프레임에서 행동과 반응을 전개하고, FL2V는 첫·마지막 프레임 사이의 관찰 가능한 변화에 집중한다. R2V는 참조 주체 정의·요약·보존 분석과 구체적인 샷 묘사를 반환한다. 서버가 section·shot·timestamp를 조립하며 첫 샷의 timeline도 유지한다. 예시는 구조만 보여 주고 실제 사용자 장면에 복사하지 않도록 지시한다. 각 구간의 clock은 0초부터 시작하며 후속 구간의 mode는 선택된 continuation mode를 따른다.

실제 선택 목록에서 생성한 reference manifest가 Picture·Video·Audio 번호와 역할의 기준이다. 이미지는 labeled preview를 보고 묘사하고, preview가 없는 참조는 보거나 들었다고 가정하지 않는다. 후속 구간의 Picture 1은 생성 전인 마지막 프레임이므로 실제로 관찰했다고 주장하지 않는다. 대사·가사·화면 글자는 원문과 문장부호를 보존하고, 설명문만 선택 언어로 작성한다.

사용자가 제공한 `MiniMax_H3_Video_Prompt_Assistant_1.rtf`에서 카메라 일관성, 참조별 유지·변경 조건, 행동의 중간 과정 규칙을 선별했다. 각 shot은 시작 상태에서 접촉·자세·위치·물체 상태의 관찰 가능한 변화를 거쳐 요청된 결과에 도달하도록 묘사한다. 이 단계를 나누기 위해 불필요한 동작이나 cut을 추가하지 않는다. 카메라의 위치·방향·초점거리를 구분하고 같은 요소의 상반된 동작은 시간 순서로 표현한다. 이동 뒤 정지, tracking과 pan, dolly zoom처럼 가능한 조합은 유지한다. 참조는 사용자와 manifest가 지정한 역할에 해당하는 속성을 보존하고 요청된 의상·배경·동작 변경을 구분한다. R2V retention_analysis에는 구체적인 유지 속성·요청된 변경·참조 강도를 명시하며 역할 밖의 변경을 정체성 손실로 취급하지 않는다.

RTF의 인터뷰·언어 질문·최종 확인·코드블록 출력은 도입하지 않는다. 기존 JSON 출력, 설명 언어 선택, 독립 오디오 참조, 구간 연결 계약을 유지한다.

참조 역할의 판단 예시도 명시한다. 정체성만 제공하는 이미지는 Subject 정의 안에서 출처로 인용하고 보존 판단은 해당 Subject에 기록한다. 이미지 자체가 독립적인 프레임·구도 anchor일 때만 별도 Picture 보존 항목을 만든다. 정체성만 참조한 얼굴·머리를 유지하면서 요청대로 의상·배경을 바꾼 경우 그 정체성 역할은 fully_preserved다. 음색만 참조하고 원음을 복사하지 않는 오디오는 reference이며 visual-only attribute_transfer를 사용하지 않는다. Subject label은 angle bracket 형식을 유지한다.

참고한 공개 자료:

- https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt
- https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt
- https://github.com/cushycrux/H3_LLM_Instructions/blob/main/H3_LLM_Instructions.txt
- https://huggingface.co/MiniMaxAI/MiniMax-H3/discussions/28
- https://comfy.icu/models/2851101/MiniMax-H3-with-all-Local-LLM-System-Prompts

Comfy.ICU 링크는 minimaxH3WithAllLocal_v10.zip(31,619 bytes, Civitai version 3219638)을 가리킨다. 다운로드는 HTTP 401 인증 요구로 ZIP 내부를 직접 열지 못했다. 페이지가 출처로 명시한 공개 원문을 비교했으며, 첫 프레임의 상태에서 행동으로 진행하는 방식·카메라 표현·화자와 대사 태그는 참고했다. 원문 일부의 [Xs-Ys] 시간 구간, 별도 audio section 배제 지시는 최신 공식 가이드와 달라 적용하지 않았다. ZIP 원문을 복사하거나 새 ComfyUI node·GGUF runtime을 설치하지 않는다.

YuE2 music enhancement keeps Style concise (language, genre, vocals, BPM, instruments and production), excludes lyrics/ABC from Style, and keeps only singable words plus section tags in Lyrics. Short durations receive compact structures; explicit instrumental requests can return `[Instrumental]`.

Music vLLM structured output: Style is `{language, genre, vocals, tempo_bpm, instruments, mood, production}`; Lyrics is `{sections: [{kind, lines}]}`. Extra keys, wrong types, tags/newlines in raw fields and unselected languages are rejected in server validation. The server orders Style fields, adds BPM, generates enum section tags and joins lyric lines/sections. The public response remains `{contents}` for editable UI proposals. Invalid provider output is attached to the existing error audit; no free-form fallback is used.

Qwen Image 2.1의 vLLM 개선은 IMAGE_EDIT_PROMPT_ENHANCEMENT_SYSTEM_PROMPT를 사용한다. 자연어 수정 지시만 출력하고 원문 언어·읽을 텍스트·변경/유지 조건·참조 관계를 보존한다. 입력 이미지를 볼 수 없음을 명시해 내용을 지어내지 않도록 한다. 태그와 설명을 추가하지 않는다.
