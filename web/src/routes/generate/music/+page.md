# 음악 생성 화면

`+page.svelte`는 MiniMax-Music3 local generation 화면이다.

- 입력: 음악 설명, optional 가사, 10-300초 최대 길이, optional seed
- 빈 가사: 연주곡 generation
- 상태: global generation job store의 SSE progress, queue position, elapsed time, cancel
- 결과: Storage signed URL을 browser native audio player와 download link에 연결
- 복구: page load 때 options와 latest music generation을 읽고 active job 또는 latest completed audio를 표시

MODEL 영역에는 model attribution requirement에 따라 `MiniMax-Music3`를 눈에 띄게 표시한다.
