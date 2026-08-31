# Generation job store

`generation-jobs.svelte.ts`는 이미지·동영상·3D generation job과 SSE 연결을 route가 아닌 앱 전역에서 소유한다.

- 생성 요청이 `202`를 반환하면 job을 등록하고 해당 backend SSE endpoint를 구독한다.
- 화면 이동으로 생성 페이지가 unmount되어도 서버가 처리 중인 job의 SSE 연결은 유지된다.
- 앱 시작 시 `GET /generation/active`를 호출해 현재 사용자의 `queued`·`processing` DB row만 복구하고 해당 SSE에 다시 연결한다.
- terminal event는 메모리 상태에 반영한다. `completed`, `failed`, `cancelled`는 terminal 상태로 취급하며 생성 화면의 대기 promise와 SSE 연결을 종료한다. 생성 화면은 store의 가장 최근 job을 결과 패널에 가져오지 않고, 해당 화면에서 새로 등록한 job만 표시해 완료된 이전 결과가 새 생성 전 결과물로 보이지 않게 한다.
- 3D job은 `generation/3d/{prompt_id}/events`를 구독하고 같은 경로의 cancel API를 사용한다. SSE의 `stage`와 완료된 `model` URL·파일 정보를 보관해 TRELLIS.2 화면이 단계 중심 진행 상태와 결과 모델을 표시한다.
