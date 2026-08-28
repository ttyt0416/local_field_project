# Generation job store

`generation-jobs.svelte.ts`는 이미지·동영상 generation job과 SSE 연결을 route가 아닌 앱 전역에서 소유한다.

- 생성 요청이 `202`를 반환하면 job을 등록하고 해당 backend SSE endpoint를 구독한다.
- 화면 이동으로 생성 페이지가 unmount되어도 연결을 중단하지 않는다.
- SSE 연결이 종료되면 지수 backoff로 재연결하고, `completed`·`failed`가 되면 terminal 상태로 멈춘다.
- active job은 localStorage에 저장해 새로고침 후 backend SSE에 다시 연결한다.
- 완료 결과 URL과 실패 메시지를 전역 상태로 보관하며 root layout이 모든 화면에 상태를 표시한다.
- 실제 생성은 backend와 ComfyUI가 담당하고 store는 backend SSE만 소비한다.
