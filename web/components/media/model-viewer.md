# 3D model viewer

`inspectRigging`을 켜면 실제 GLB의 관절 수·스킨 메시 수·애니메이션 수를 표시하고 기본 자세의 뼈대를 겹쳐 보여 준다. model-viewer 공개 hotspot API로 관절 좌표를 화면에 투영하며 회전·확대·크기 변경을 따라간다. 주황 점은 관절, 청록 선은 부모 연결이고 메시 뒤의 뼈대도 표시한다. `뼈대 보기/숨기기`로 표면과 비교한다. 원본 파일이나 자세를 변경하지 않는다.

서버 모델은 공용 `apiBlob`으로 인증 요청한 뒤 Blob URL로 표시한다. 요청 제한시간은 큰 GLB를 위해 120초로 설정한다. source 변경·unmount 시 이전 응답을 무시하고 Blob URL을 해제한다. 파일 수신 전에는 custom element를 생성하지 않으며, 요청·뷰어 모듈 로드 오류를 Toast로 표시한다. 생성 결과와 리깅 원본의 API 경로를 사용해 Storage CORS에 의존하지 않는다.

공용 3D 미디어 컴포넌트는 브라우저에서 `@google/model-viewer`를 지연 로드하고 로컬 Blob 또는 서버 URL의 모델을 표시한다. `model-viewer` 태그 이름은 상수 literal로 유지해 Svelte가 custom element 속성 타입을 올바르게 확인하도록 하고, custom element는 컨테이너 높이를 채운다. 서버 모델은 로딩 shimmer와 실패 상태를 제공하며 camera controls, 자동 회전, poster, 그림자, 노출 설정을 지원한다.
