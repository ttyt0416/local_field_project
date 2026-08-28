# 미디어 Storage 메타데이터

`image_generations.storage_file_id`와 `video_generations.storage_file_id`는 실제 바이트가 아니라 독립 Storage 서비스의 파일 식별자만 보관한다.

`media_assets`는 생성 요청 시 새로 저장되었거나 기존 Storage에서 재사용된 이미지·동영상·오디오 입력을 사용자별로 추적한다. 생성 이미지와 생성 영상도 각 generation 레코드의 Storage 연결을 통해 동일한 재사용 미디어 라이브러리 조회에 포함한다. `storage_file_id`는 재사용을 위한 unique key이며, 생성 결과를 input으로 재사용하면 `generation_input`으로 upsert한다. `source_type`은 직접 저장된 사용 콘텐츠, 이미지 생성 결과, 영상 생성 결과를 구분하는 표시값이며 향후 i2i 등 다른 생성 방식도 같은 계약을 재사용한다.

`video_generations`는 I2V·FL2V·R2V mode, ComfyUI 작업 ID, 입력 Storage file ID 목록, 결과 Storage file ID, 상태, 조회수와 favorite 상태를 저장한다. 기존 테이블에는 시작 시 migration statement가 필요한 조회수·favorite 컬럼을 기본값과 함께 추가한다.

`presets`는 사용자별 설정 모음이다. `type`으로 프리셋 종류를 구분하고 현재는 `t2i`를 사용하며, 같은 이름도 여러 개 저장할 수 있고 UUID로 수정·삭제 대상을 구분한다. `is_default`는 사용자와 프리셋 타입 조합별로 최대 1개만 허용한다.
