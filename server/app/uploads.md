# 업로드 콘텐츠 API

`GET /uploads`는 로그인한 사용자가 업로드한 이미지·동영상·오디오 콘텐츠만 반환한다. 생성 이미지·동영상은 보관함에서 확인하며 기본 업로드 목록에는 포함하지 않는다. 결과는 사용자 소유권으로 제한하고 Storage signed URL을 미리 발급한다. `page`는 1부터 시작하고 page size는 10으로 고정하며, 응답은 `items`, `page`, `page_size`, `total_count`, `total_pages`를 포함한다.

`search`는 filename 부분 검색이고, `sort`는 `latest`·`oldest`·`name` 중 하나다. 업로드 화면은 이 두 파라미터를 서버에 전달해 이름 검색과 정렬을 수행한다. 콘텐츠 종류 선택은 공용 `components/tabs/tab.svelte`를 사용한다.

`DELETE /uploads/{file_id}`는 먼저 현재 사용자 소유의 `media_assets` row를 확인한 뒤 Storage 파일을 삭제하고 DB row를 삭제한다. 소유하지 않은 file ID는 `404`이며, Storage 삭제 실패 시 DB row를 유지하고 오류를 반환한다. 화면은 삭제 전 확인 modal과 비동기 loading 상태를 표시한다.

동영상 생성 선택 modal은 `include_generated=true`를 함께 보내 업로드 콘텐츠와 생성 이미지·동영상을 하나의 선택 목록으로 조회할 수 있다. `search`, `sort`(`latest`·`oldest`·`name`), `media_kind` 쿼리로 모달의 검색·정렬·입력 종류 필터를 서버에서 처리한다.

`media_assets`는 동영상 생성에 사용자가 제공한 입력 콘텐츠를 공통 계약으로 추적한다. 생성 이미지와 동영상은 동영상 생성 선택 modal에서만 각 generation 테이블의 Storage 파일 연결을 통해 함께 조회한다. `source_type`은 생성 결과와 업로드 콘텐츠를 구분하는 표시값이다.
