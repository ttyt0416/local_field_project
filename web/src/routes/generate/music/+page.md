# 음악 생성 화면

`+page.svelte`는 MiniMax-Music3 local generation 화면이다.

- 입력: 음악 설명, optional 가사, 10-300초 최대 길이, optional seed
- 개선: description과 lyrics를 각각 따로 vLLM에 요청하고 `한글`, `영어`, `일어` output language를 복수 선택한다. 빈 lyrics에서는 `가사 생성`, 값이 있으면 `가사 개선`을 실행한다. 각 개선 결과는 별도 textarea에서 수정할 수 있고 improvement가 켜진 동안 해당 값만 generation request에 사용한다.
- 상태: global generation job store의 SSE progress, queue position, elapsed time, cancel
- 결과: Storage signed URL을 browser native audio player와 download helper에 연결
- 복구: page load 때 options와 latest music generation을 읽고 active job 또는 latest completed audio를 표시

Ready 상태에서는 service detail 문구를 표시하지 않으며, lyrics 아래 별도 안내 문구도 두지 않는다. MODEL 영역에는 `MiniMax-Music3`를 표시한다.
