# Generation job store

`generation-jobs.svelte.ts`는 이미지·동영상 generation job과 SSE 연결을 route가 아닌 앱 전역에서 소유한다.

- 생성 요청이 `202`를 반환하면 job을 등록하고 해당 backend SSE endpoint를 구독한다.
- 화면 이동으로 생성 페이지가 unmount되어도 서버가 처리 중인 job의 SSE 연결은 유지된다.
- 앱 시작 시 `GET /generation/active`를 호출해 현재 사용자의 `queued`·`processing` DB row만 복구하고 해당 SSE에 다시 연결한다.
- terminal event는 메모리 상태에 반영하며 generation processing 상태를 브라우저 저장소에 기록하지 않는다.
