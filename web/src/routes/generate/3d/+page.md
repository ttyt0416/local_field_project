# 3D 작업 탭

`/generate/3d`는 공용 Layout·Typography·Tab을 사용한다. 기본 MESH 탭은 mesh-panel.svelte, RIGGING 탭은 rigging-panel.svelte를 `{#if}`/`{:else}`로 조건부 렌더링한다. 비활성 탭의 컴포넌트는 unmount되며 실제 생성 작업과 SSE는 서버 및 앱 전역 generation job store가 유지한다. 기존 MESH 화면은 mesh-panel로 이동했다.
