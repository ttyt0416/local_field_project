# 미디어 Storage 메타데이터

`image_generations.storage_file_id`와 `video_generations.storage_file_id`는 실제 바이트가 아니라 독립 Storage 서비스의 파일 식별자만 보관한다. `size_bytes`는 저장 결과의 실제 파일 용량을 별도로 보관한다.

`media_assets`는 생성 요청 시 새로 저장되었거나 기존 Storage에서 재사용된 이미지·동영상·오디오 입력을 사용자별로 추적한다. `list_reusable_media`의 기본 조회는 생성 결과 파일을 제외한 업로드 콘텐츠만 반환하며, 동영상 선택 모달이 `include_generated=true`를 요청할 때만 생성 이미지·영상 generation 레코드도 합친다. `storage_file_id`는 재사용을 위한 unique key이며, 생성 결과를 input으로 재사용해도 generation 출력 파일은 업로드 목록에 중복 표시하지 않는다. `source_type`은 직접 저장된 사용 콘텐츠, 이미지 생성 결과, 영상 생성 결과를 구분하는 표시값이며 향후 i2i 등 다른 생성 방식도 같은 계약을 재사용한다.

`video_generations`는 I2V·FL2V·R2V mode, ComfyUI 작업 ID, 입력 Storage file ID 목록, 결과 Storage file ID, 상태, fps, 조회수와 favorite 상태를 저장한다. 영상 fps 기본값은 24이다. `image_generations`와 `video_generations`는 생성 시작 시각 `created_at`, terminal 시각 `completed_at`, 누적 소요 시간 초 단위 `elapsed_seconds`를 저장한다. active row의 elapsed는 현재 시각과 시작 시각을 비교해 반환하고 worker가 주기적으로 DB에 반영하며, 완료·실패 시 고정한다. 기존 테이블에는 시작 시 migration statement가 필요한 컬럼을 기본값과 함께 추가한다.

`presets`는 사용자별 설정 모음이다. `type`으로 프리셋 종류를 구분하고 현재는 `t2i`를 사용하며, 같은 이름도 여러 개 저장할 수 있고 UUID로 수정·삭제 대상을 구분한다. `is_default`는 사용자와 프리셋 타입 조합별로 최대 1개만 허용한다.

`image_generations`와 `video_generations` 보관함 목록은 사용자·검색·정렬·favorite 필터를 DB에 적용하고 page size 10과 `LIMIT/OFFSET`으로 페이지를 반환한다. 목록 조회는 전체 개수와 완료 개수를 함께 계산해 API가 `total_count`, `completed_count`, `total_pages`를 제공한다. 편집 결과는 `source_generation_id`와 `is_edited`가 설정된 새 generation row로 저장되어 원본 row와 Storage 파일을 보존한다. 이미지 편집 결과는 브라우저 Canvas Blob을 업로드하고, 동영상 편집 결과는 서버 FFmpeg로 H.264/AAC MP4를 만든다.

`model_downloads`는 Civitai 모델 download job의 version ID, 모델 타입, 파일명, target path, 상태, 진행 바이트와 오류만 저장한다. `target_path`는 `COMFYUI_MODELS_PATH` 아래의 모델 타입 폴더와 사용자가 지정한 안전한 상대 `subfolder`를 합친 최종 저장 경로다. Civitai token과 signed download URL은 저장하지 않는다. 사용자별 version·타입·파일 active job은 unique index로 중복을 막으며, failed 또는 cancelled job은 retry API로 다시 queued 상태가 된다. cancel API는 queued/downloading job을 cancelled로 바꾸고 `.part` 파일을 삭제한다. startup worker는 `downloading` job을 `queued`로 되돌리고, `.part` 파일과 HTTP Range를 이용해 재시도한다.
