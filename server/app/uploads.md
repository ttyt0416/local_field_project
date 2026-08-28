# 콘텐츠 라이브러리 API

`GET /uploads`는 로그인한 사용자가 소유하거나 생성·사용한 이미지·동영상·오디오 콘텐츠를 하나의 재사용 라이브러리로 반환한다. 결과는 사용자 소유권으로 제한하고 Storage signed URL을 미리 발급한다.

`media_assets`는 직접 저장된 generation input과 향후 다른 생성 방식에서 사용되는 콘텐츠를 공통 계약으로 추적한다. 생성된 이미지와 동영상은 각 generation 테이블의 Storage 파일 연결도 같은 라이브러리 조회에 포함한다. `source_type`은 생성 결과와 사용된 콘텐츠를 UI에서 구분하는 표시값이다.
