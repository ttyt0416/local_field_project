# 3D 모델 생성 화면

선택 전에는 소스 이미지 선택 버튼만 표시하고 `기기 또는 보관함에서 이미지를 선택해 주세요` 문구의 빈 미리보기 섹션은 표시하지 않는다.

`/generate/3d`의 MESH 탭은 동영상 생성 화면을 참고한 `mesh-source-modal.svelte`로 기기 이미지 또는 보관함 이미지를 한 장 선택한다. 기기 파일은 multipart `files`와 `payload.source.file_index=0`으로, 보관함 이미지는 파일 재업로드 없이 `payload.source.file_id`로 전송한다. 새 선택은 기존 선택을 대체하고 선택 해제는 두 소스를 모두 비운다. URL이 없는 보관함 항목도 파일명과 함께 선택 상태를 유지한다. 품질 프리셋은 미리보기·표준·고품질을 각각 `preview`·`standard`·`high`로 전송하며, 무작위 또는 고정 Seed, 배경 제거를 설정한다.

생성 요청은 `POST /generation/3d`를 사용한다. 수락된 job은 전역 generation job store에 `kind=3d`로 등록해 화면 이동 뒤에도 SSE lifecycle을 유지하고, reload 후에는 `GET /generation/active`로 active job의 SSE 감시를 복구한다. route-local 결과 panel은 임의의 latest job을 선택하지 않고 해당 화면에서 시작한 job에만 붙는다. 취소는 `POST /generation/3d/{prompt_id}/cancel`을 호출한다. 3D 단계마다 작업량이 다르므로 단일 percentage를 정확한 진행률처럼 표시하지 않고 서버 `stage`를 한국어 작업 단계로 표시한다. 완료된 GLB 결과는 공용 `model-viewer.svelte`로 회전·확대 가능한 미리보기를 제공하고 `/vault/3d/{generation_id}` 상세로 연결한다.

`GET /generation/3d/options`의 `ready`·`detail`을 읽어 모델 준비 상태 안내를 표시하고 준비되지 않으면 생성 버튼과 제출을 막는다. 이미지·프리셋·Seed·배경 제거 폼과 결과 UI는 유지한다.

TripoSplat 연결: 기존 이미지·배경 제거·Seed UI와 GLB 결과를 유지한다. 프리셋은 포인트 수·샘플링 단계에 맞춰 표시한다. 모델이 고정 전처리 여백을 적용하므로 기존 여백 입력은 제거한다. 컬러 GLB 메시 변환이 실험적이라는 안내를 표시한다.

기존 메시 생성 화면을 이 컴포넌트로 이동했다. 상위 페이지가 Layout과 탭을 소유한다. MESH의 입력·프리셋·TripoSplat 실행·결과·취소를 유지하고 전역 store의 진행 중인 MESH job을 다시 표시한다.
