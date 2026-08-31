# 3D model viewer

공용 3D 미디어 컴포넌트는 브라우저에서 `@google/model-viewer`를 지연 로드하고 로컬 Blob 또는 서버 URL의 모델을 표시한다. `model-viewer` 태그 이름은 상수 literal로 유지해 Svelte가 custom element 속성 타입을 올바르게 확인하도록 하고, custom element는 컨테이너 높이를 채운다. 서버 모델은 로딩 shimmer와 실패 상태를 제공하며 camera controls, 자동 회전, poster, 그림자, 노출 설정을 지원한다.
