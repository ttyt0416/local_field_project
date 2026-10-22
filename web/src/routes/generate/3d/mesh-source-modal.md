# MESH 소스 이미지 선택

동영상 생성 화면의 단일 이미지 선택 모달을 참고한 3D 전용 선택 컴포넌트다. 공용 Modal·Tab·ImageMedia·SearchBar·버튼을 재사용한다. 기본값은 보관함의 생성 이미지이며 기기 저장소로 전환해 이미지 한 장을 고를 수도 있다. 단일 항목의 선택 버튼은 즉시 parent에 저장된 파일 정보 또는 File을 전달하고 모달을 닫는다.

보관함 목록은 동영상 화면과 같은 `GET /uploads`에 include_generated=true·media_kind=image·source(uploaded/generated)·search·sort·page를 전달한다. 생성 이미지에는 공용 presets의 모델 family·T2I/I2I 분류를 추가하고 MOSS·Qwen의 지원 방식 제약도 동일하게 적용한다. 검색·정렬·필터 변경은 첫 페이지를 조회한다. 새 요청 ID와 mount 상태를 확인해 늦은 응답이나 닫힌 모달 응답이 상태를 덮어쓰지 않게 한다. 모든 조회 오류는 parent의 기존 Toast로 전달한다.

외부 Storage의 signed URL은 동영상 화면과 같이 external 이미지로 표시한다. 파일 다운로드·재업로드 없이 file_id를 기존 3D 생성 API에 전달하며 소유권 검증은 기존 서버가 수행한다.
