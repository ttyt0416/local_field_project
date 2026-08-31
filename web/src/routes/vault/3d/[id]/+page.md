# 3D 모델 상세

`/vault/3d/[id]`는 `GET /vault/3d/{id}`로 TRELLIS.2 결과와 프리셋·Seed·배경 제거·오브젝트 여백·소스 파일 생성 파라미터를 불러온다. GLB 결과는 공용 `components/media/model-viewer.svelte`로 표시해 회전·확대·자동 회전을 지원하고, 서버가 제공한 소스 이미지가 있으면 poster와 별도 소스 카드로 재사용한다.

상세 화면은 기존 이미지·동영상 상세와 같은 패턴으로 모델 다운로드, `PATCH /vault/3d/{id}/favorite` 즐겨찾기, 확인 모달 뒤 `DELETE /vault/3d/{id}` 삭제를 제공한다. 삭제가 완료되면 `/vault?tab=3d`로 돌아간다. 모든 서버 통신 실패는 negative toast로 표시하고 비동기 버튼은 처리 중 loading 및 disabled 상태를 유지한다.
