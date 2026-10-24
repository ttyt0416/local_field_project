# 다운로드 출처와 작업

다운로드 관리의 Civitai·Hugging Face 탭은 공통 DownloadJob 진행 목록을 사용한다. Civitai의 version_id와 Hugging Face의 source_repo·고정 source_revision·source_filename을 구분하며 signed URL이나 토큰은 포함하지 않는다. 두 출처 모두 기존 모델 종류와 저장 하위 폴더, 작업 ID 기반 중단 API를 공유한다.
