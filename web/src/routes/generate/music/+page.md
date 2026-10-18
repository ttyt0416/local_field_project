# 음악 생성 화면

`+page.svelte`는 YuE2 로컬 음악 생성 화면이다.

- 입력: 음악 설명, optional 가사, 10-900초 최대 길이, optional seed
- 개선: description과 lyrics를 각각 따로 vLLM에 요청하고 `한글`, `영어`, `일어` output language를 복수 선택한다. 빈 lyrics에서는 `가사 생성`, 값이 있으면 `가사 개선`을 실행한다. 각 개선 결과는 별도 textarea에서 수정할 수 있고 improvement가 켜진 동안 해당 값만 generation request에 사용한다.
- 상태: global generation job store의 SSE progress, queue position, elapsed time, cancel
- 결과: Storage signed URL을 browser native audio player와 download helper에 연결
- 복구: page load 때 options와 latest music generation을 읽고 active job 또는 latest completed audio를 표시

Ready 상태에서는 service detail 문구를 표시하지 않으며, lyrics 아래 별도 안내 문구도 두지 않는다. MODEL 영역에는 `YuE2`를 표시한다. options의 `service_available=false`이면 생성 버튼과 제출을 막고 안내를 표시한다. 폼과 기존 결과·프롬프트 개선 기능은 유지한다.

YuE2 연결: 최대 길이 10–900초(기본 120), 작곡 방식 `full`·`melody`·`off`, 선택 ABC 악보 입력을 지원한다. 가사와 Style은 분리하고 vLLM 개선 기능·기존 결과 재생·다운로드를 유지한다. 길이는 상한이며 실제 곡은 먼저 종료될 수 있다.

Music vLLM structured output: Style is `{language, genre, vocals, tempo_bpm, instruments, mood, production}`; Lyrics is `{sections: [{kind, lines}]}`. Extra keys, wrong types, tags/newlines in raw fields and unselected languages are rejected in server validation. The server orders Style fields, adds BPM, generates enum section tags and joins lyric lines/sections. The public response remains `{contents}` for editable UI proposals. Invalid provider output is attached to the existing error audit; no free-form fallback is used.
