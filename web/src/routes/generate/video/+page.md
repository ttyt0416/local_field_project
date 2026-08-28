# MiniMax H3 동영상 생성 화면

I2V·FL2V·R2V를 탭으로 선택한다. 로컬 파일은 브라우저 상태에만 보관하고 생성 submit 시 multipart 요청으로 전송한다. 콘텐츠 라이브러리에서 선택한 기존 파일은 `file_id`로 전송해 서버가 소유권 확인 후 재사용한다. R2V는 reference 이미지·동영상·오디오를 사용한다.

페이지는 생성 결과와 서버가 기록한 상태를 표시한다. 생성 버튼을 누르면 Backend가 ComfyUI queue를 제출하고, 화면을 이동해도 서버 worker가 계속 처리한다. 프런트는 전역 generation job store를 통해 SSE를 구독하므로 route가 바뀌어도 상태·완료 결과·실패를 유지한다. 실제 Storage 업로드와 ComfyUI queue 제출은 생성 버튼을 누른 뒤에만 시작한다. 모바일 submit 버튼은 불투명한 하단 고정 영역에 표시하고 데스크톱에서는 폼 흐름으로 되돌린다.
