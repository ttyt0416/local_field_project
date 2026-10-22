# SkinTokens 리깅 화면

RIGGING 탭은 GLB(최대 200 MiB) 업로드 또는 보관함의 완료된 MESH 결과를 입력으로 사용한다. 공용 ModelViewer·Select·Tab·버튼·Toast와 기존 API helper, generation job store를 재사용한다. 보관함은 기존 paginated 3D API를 사용하며 더 불러오기에서 다음 페이지를 가져온다. 파일과 보관함 모델은 동시에 제출하지 않는다.

초기화 시 실행 서비스 readiness를 확인하며 준비되지 않으면 자동 리깅을 비활성화한다. Temperature(0.1~2)와 Beam 수(1~10, 기본 10)는 고급 설정에 둔다. 생성 수락 후 kind=3d, generationMode=rigging으로 전역 SSE를 구독한다. 모드별 최근 메모리 job을 복원해 탭 전환 후 상태와 완료 결과를 다시 볼 수 있다. 업로드 중 재제출을 막고 모든 통신 오류를 Toast로 표시한다.

결과는 원본 색상·재질·크기를 보존한 GLB이며 뼈대와 스킨 가중치를 포함한다. 움직임 생성·리타게팅·뼈대 편집은 제공하지 않는다. 파일 다운로드와 보관함 상세 링크를 제공한다.
