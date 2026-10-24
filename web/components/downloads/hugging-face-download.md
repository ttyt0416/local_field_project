# Hugging Face 다운로드 패널

다운로드 관리의 Hugging Face 탭에서 모델 저장소·파일·폴더 링크와 선택 리비전을 조회한다. 모델 종류는 사용자가 직접 선택한다. 파일 목록은 경로 검색·단일 선택을 제공하며 선택한 경로를 별도 표시한다. 공용 ModelFolderPicker로 저장 위치를 선택하고 조회된 repo·고정 commit·원본 파일 경로만 enqueue API에 보낸다. 토큰과 다운로드 URL은 프런트엔드에서 받지 않는다.

성공한 DownloadJob은 ondownload로 부모의 공통 진행 목록에 추가한다. 조회·다운로드 중 busy binding으로 탭 전환을 막고 버튼은 loading/disabled 상태를 제공한다. 입력 변경·새 조회·unmount 후 오래된 응답을 무시한다. API 오류는 inline 안내와 Toast로 표시한다. 다운로드 요청 성공 시 입력과 선택 상태를 초기화한다.
