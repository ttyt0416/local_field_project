# 미디어 Storage 메타데이터

`image_generations.storage_file_id`와 `video_generations.storage_file_id`, `music_generations.storage_file_id`, `three_d_generations.storage_file_id`는 실제 바이트가 아니라 독립 Storage 서비스의 파일 식별자만 보관한다. `size_bytes`는 저장 결과의 실제 파일 용량을 별도로 보관한다. `image_generations` row는 원문 `prompt`와 nullable `improved_prompt`, `model_family`, `generation_mode`, nullable `source_file_id`·`source_filename`, `denoise`, positive·negative prefix와 각각의 raw prompt body를 저장해 Anima·Illustrious·Krea2 T2I/I2I lifecycle을 같은 방식으로 관리한다. Krea2 I2I request는 dedicated style-reference workflow가 제공될 때까지 reject되므로 현재 생성 row는 Krea2 T2I에서만 만들어진다. 3D row는 source image `source_file_id`와 결과 GLB `storage_file_id`를 분리하고, 결과 MIME은 `model/gltf-binary`로 고정한다.

`media_assets`는 생성 요청 시 새로 저장되었거나 기존 Storage에서 재사용된 이미지·동영상·오디오 입력을 사용자별로 추적한다. `list_reusable_media`의 기본 조회는 생성 결과 파일을 제외한 업로드 콘텐츠만 반환하며, 동영상 선택 모달이 `include_generated=true`를 요청할 때만 생성 이미지·영상 generation 레코드도 합친다. `storage_file_id`는 재사용을 위한 unique key이며, 생성 결과를 input으로 재사용해도 generation 출력 파일은 업로드 목록에 중복 표시하지 않는다. `source_type`은 직접 저장된 사용 콘텐츠, 이미지 생성 결과, 영상 생성 결과를 구분하는 표시값이며 향후 i2i 등 다른 생성 방식도 같은 계약을 재사용한다.

`video_generations`는 I2V·FL2V·R2V mode, public ComfyUI root `prompt_id`, 현재 실행 중인 internal `active_prompt_id`, 선택 checkpoint, LoRA name·strength JSONB 목록, `steps`, `use_pdd`, 입력 Storage file ID 목록, 결과 Storage file ID, 상태, fps, 조회수와 favorite 상태를 저장한다. learned 3D upscale row는 legacy `upscale` boolean과 독립적으로 `upscale_mode`, base MP·width·height, target MP·width·height, derived `upscale_scale`, `upscale_model`을 저장한다. long video sequence는 실행용 `segment_prompts`, 사용자 원문 `input_segment_prompts`, 사용자 검토 후 improved output `improved_segment_prompts`, `segment_durations`, `continuation_mode`, ordered `reference_image_file_ids`, 0-based `segment_index`, internal `segment_file_ids`를 additive JSONB columns에 보관한다. active ID claim은 NULL로 mark한 뒤 only one reconciler가 selected continuation workflow로 advance하거나 final concat output으로 complete하도록 조건부 update를 사용한다. `music_generations`는 Music 3의 prompt/client ID, status, music description, lyrics, actual seed, requested max duration, 결과 Storage metadata, optional actual duration, file size, 조회수와 favorite 상태를 저장한다. 영상 fps 기본값은 24이다. `image_generations`와 `video_generations`는 생성 시작 시각 `created_at`, terminal 시각 `completed_at`, 누적 소요 시간 초 단위 `elapsed_seconds`를 저장한다. active row의 elapsed는 현재 시각과 시작 시각을 비교해 반환하고 worker가 주기적으로 DB에 반영하며, 완료·실패 시 고정한다. 기존 테이블에는 시작 시 migration statement가 필요한 컬럼을 기본값과 함께 추가한다.

`presets`는 사용자별 설정 모음이다. `type`으로 프리셋 종류를 구분하고 현재는 `t2i`를 사용하며, 같은 이름도 여러 개 저장할 수 있고 UUID로 수정·삭제 대상을 구분한다. `is_default`는 사용자와 프리셋 타입 조합별로 최대 1개만 허용한다.

`image_generations`와 `video_generations` 보관함 목록은 사용자·검색·정렬·favorite 필터를 DB에 적용하고 page size 10과 `LIMIT/OFFSET`으로 페이지를 반환한다. 목록 조회는 전체 개수와 완료 개수를 함께 계산해 API가 `total_count`, `completed_count`, `total_pages`를 제공한다. 필터 전체 삭제용 query는 같은 검색·favorite 조건을 pagination 없이 snapshot하고, Storage 삭제 전에는 snapshot 밖 generation의 같은 `storage_file_id` 참조도 확인한다. 편집 결과는 `source_generation_id`와 `is_edited`가 설정된 새 generation row로 저장되어 원본 row와 Storage 파일을 보존한다. 이미지 편집 결과는 브라우저 Canvas Blob을 업로드하고, 동영상 편집 결과는 서버 FFmpeg로 H.264/AAC MP4를 만든다.

`model_downloads`는 모델 download job의 provider, Civitai version ID 또는 Hugging Face repo·고정 commit·원본 파일 경로, 모델 타입, 파일명, target path, 상태, 진행 바이트와 오류를 저장한다. 기존 row에는 provider=civitai를 기본값으로 추가한다. Hugging Face는 내부 version_id=0과 독립 source 필드를 쓰며 API의 version_id는 null이다. `target_path`는 `COMFYUI_MODELS_PATH` 아래의 모델 타입 폴더와 사용자가 지정한 안전한 상대 `subfolder`를 합친 최종 저장 경로다. Civitai token과 signed download URL은 저장하지 않는다. 새 unique index는 사용자·출처·version·타입·파일 index·repo·commit·원본 경로의 active job을 구분한다. 새 index를 먼저 만든 뒤 이전 Civitai 전용 index를 제거해 출처가 다른 작업을 허용하며 기존 Civitai 중복 방지는 유지한다. failed 또는 cancelled job은 retry API로 다시 queued 상태가 된다. cancel API는 queued/downloading job을 cancelled로 바꾸고 `.part` 파일을 삭제한다. startup worker는 `downloading` job을 `queued`로 되돌리고, `.part` 파일과 HTTP Range를 이용해 재시도한다. Download 목록은 기본적으로 최근 row를 반환하고 `active_only`일 때 SQL에서 `queued`·`downloading`만 제한한다.

`api_error_logs.provider_response`는 failed provider call이 실제로 반환한 decoded JSON response를 JSONB로 저장한다. prompt and credential은 넣지 않으며, response의 `choices`, `finish_reason`, `usage`, incomplete structured content를 Error DB에서 같은 503 row와 함께 확인해 token budget 소진 위치를 진단한다.

`has_active_model_downloads_under`는 폴더 변경·삭제 전에 모든 사용자의 queued/downloading target_path를 조회한다. 디렉터리 뒤 slash를 포함한 문자열 prefix를 비교하므로 형제 폴더를 혼동하거나 이름의 `%`·`_`를 SQL wildcard로 해석하지 않는다. 파일 내용이나 토큰은 조회하지 않는다.

image_generations.reference_images JSONB는 추가 참조 이미지의 file_id·filename을 순서대로 저장한다. 시작 시 기존 row에 빈 배열로 컬럼을 추가하고, crop 편집 row도 이 목록을 복사한다. Storage 참조 검사에 JSONB file_id도 포함해 다른 결과가 참조 중인 파일의 삭제를 막는다.

## MOSS

image_generations의 moss JSONB 열은 MOSS 생성 방식·레이아웃·참조 설정을 저장한다. 기본값은 빈 객체이고 기존 기록을 유지한다. 생성 insert/read와 편집본 복사에서 설정을 보존한다.

이미지 생성 기록에 prompt_enhancement_enabled BOOLEAN 기본 FALSE를 추가하고 생성·상세·편집 복사에서 유지한다. Qwen의 i2i_qwen_image_2_1 분류를 위해 presets.type을 VARCHAR(32)로 확장하며 기존 16자 열에 대한 멱등 마이그레이션을 포함한다. 운영 반영 전 검증은 동일 스키마 임시 테이블과 롤백을 사용한다.

3D row는 `generation_mode=mesh|rigging`, `rigging_options` JSONB와 `error_message`를 추가로 저장한다. 기존 row는 `mesh`로 유지한다. 리깅 source_file_id는 원본 GLB이고 storage_file_id는 리깅 결과 GLB다. 리깅은 품질 프리셋·Seed·배경 제거를 사용하지 않으며 기존 필수 컬럼에는 standard·0·false를 기록한다.

사용자별 download_tokens는 provider와 암호문·수정 시각을 저장한다. saved_prompts는 image/video 문장만 저장하며 두 테이블 모두 사용자 삭제 시 함께 제거한다. 스키마 추가는 IF NOT EXISTS로 반복 실행 가능하다.

Gelbooru 태그와 AnimaDex 엔트리는 별도 로컬 테이블과 trigram 검색 인덱스를 사용한다. tag_catalogue_imports는 출처별 원본 버전·마지막 성공 시각·최근 실패 원인을 보관한다. 기존 Danbooru 테이블과 벡터에는 영향을 주지 않는다.

## 동작·오류 기록

API·인증·웹 로그 쓰기는 별도 큐로 전달하고 완료를 기다리지 않는다. 기록 연결 3초·쿼리 5초·잠금 2초 제한을 적용한다. api_error_logs.error_details에 예외 체인·스택·외부 응답을 저장하고 메시지 1,000자 절단을 제거한다. 웹 로그에 event_id, client_occurred_at, visitor_id, session_id, target_path, target_context를 추가한다. 긴 URL은 TEXT로 보존하고 인덱스는 앞 512자를 사용한다. event_id 중복은 무시한다. 다운로드 실패 상태에도 원문을 저장한다.
