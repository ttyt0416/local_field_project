# Vault 이미지·동영상·3D 목록 및 관리

3D 모델 URL은 인증된 `GET /vault/3d/{generation_id}/model` 경로다. 소유권과 완료 상태를 확인하고 내부 Storage에서 읽은 GLB 바이트를 반환한다. 리깅 원본은 같은 경로의 `source=true`로 조회하며 리깅 row의 소유권을 확인한다. 브라우저에서 Storage 공개 URL의 CORS 설정에 의존하지 않으며 파일 응답은 private/no-store로 처리한다. 모델 다운로드도 이 경로를 사용한다.

`GET /vault/images`, `GET /vault/videos`, `GET /vault/3d`는 로그인한 사용자의 생성 결과를 반환한다. `search`, `sort`, `favorites_only`, `page`로 검색·정렬·즐겨찾기 필터·페이지를 처리한다. 모든 media summary/detail은 active shared generation SSE key인 `prompt_id`, `client_id`를 제공하고, 상세 API는 사용자 소유권을 확인하며 조회수를 1 증가시킨다. 3D summary/detail은 source image의 만료 읽기 URL과 GLB의 인증 조회 경로, preset, seed, stage, 파일 크기를 제공한다.

이미지 상세는 `model_family`, `generation_mode`, I2I source image URL과 `denoise`, positive·negative prefix와 raw prompt body를 함께 반환해 동일 family/mode 재생성과 prefix를 분리한 preset 저장을 지원한다. 이미지 상세는 `file_size_bytes`로 파일 용량을 표시하고, 동영상 상세는 `checkpoint`, 저장된 LoRA name·strength 목록, `steps`, `use_pdd`, `duration_seconds`, `file_size_bytes`를 제공한다. learned 3D upscale 동영상 상세는 base/target MP·dimensions, derived scale와 model provenance도 제공하고 preset 저장은 base MP와 target MP 설정을 함께 보존한다. 신규 생성·편집 결과는 저장 당시 실제 bytes를 기록하고, 기존 결과의 size가 없는 경우 상세 조회에서 Storage metadata를 보완 조회한다.

이미지 상세의 편집 버튼은 crop, 1.0x~3.0x 중앙 확대, 90도 단위 회전을 Canvas로 미리보고 `POST /vault/images/{generation_id}/edit`로 새 generation을 저장한다. `GET /vault/images/{generation_id}/source`는 편집용 인증 원본을 제공한다. `GET /vault/images/{generation_id}/download`와 `GET /vault/videos/{generation_id}/download`는 generation owner를 확인한 뒤 Local Field가 Storage bytes를 읽어 attachment response로 반환하므로 browser가 signed Storage URL을 직접 fetch하지 않는다. 이미지 lightbox의 확대·축소는 표시 크기만 변경한다.

동영상 상세의 편집 버튼은 시작·종료 시간, crop 좌표, 90도 단위 회전을 입력받아 `POST /vault/videos/{generation_id}/edit`에서 FFmpeg로 새 H.264/AAC MP4를 저장한다. 모든 편집은 원본 generation과 Storage 파일을 보존한다. `POST /vault/videos/{generation_id}/upscale`은 완료된 owner-owned Storage MP4를 R2V reference로 재사용하고, 현재 output MP보다 큰 Target MP의 새 learned H3 latent upscale job을 queue한다. 이 route는 source를 pixel-space로 변환하지 않으며 PDD를 사용하지 않는다. Vault video summary/detail은 `prompt_id`와 `client_id`를 포함해 shared generation SSE progress를 연결한다.

`DELETE /vault/images/bulk`와 단일·filtered 삭제 API는 기존 사용자 소유권·Storage 보존 규칙을 유지한다. 삭제 대상이 `queued` 또는 `processing`이면 image/video/3D의 기존 targeted Comfy cancel route를 먼저 완료한다. 취소에 실패하면 Storage와 DB를 유지한 채 delete를 실패시킨다. `DELETE /vault/images/filtered`와 `DELETE /vault/videos/filtered`는 현재 `search`·`favorites_only` 조건에 맞는 모든 page의 row를 snapshot으로 조회한다. `confirmed=true`와 화면에서 확인한 `expected_count`가 일치해야 삭제하며, 개수가 바뀌면 `409`로 중단한다.

Bulk 삭제는 삭제 가능한 Storage 파일을 먼저 모두 지운 뒤 DB row를 삭제한다. Storage 삭제 하나라도 실패하면 DB row를 유지한다. 해당 파일이 `media_assets` 또는 snapshot 밖의 다른 image/video generation에서 참조되면 Storage 원본은 보존한다.

FLUX 3 Klein 편집은 `model_family="flux3_klein"`, `generation_mode="i2i"`, `i2i_flux3_klein` preset namespace로 구분한다. 신규 family 선택에서 Krea2는 제거하며 이전 생성 데이터는 유지한다.

이미지 detail의 reference_images는 저장된 추가 참조 목록과 사용자별 읽기 URL을 반환한다. 새 참조 컬럼이 비어 있는 기존 row는 빈 목록으로 처리한다.

## MOSS SFT

MOSS SFT 생성 기록을 family 필터에서 조회한다. 상세 응답의 moss 필드는 레이아웃과 참조 모드·강도·구도 유지 설정을 재생성 화면에 전달한다.

Qwen 2.1 Turbo family(qwen_image_2_1)의 목록·상세·참조 이미지 조회를 지원한다.

이미지 상세에 prompt_enhancement_enabled를 반환하며 기존 improved_prompt가 있는 기록도 강화 활성으로 읽는다. Qwen 생성 시 LLM 강화 상태를 재생성에 복원한다.

3D summary/detail은 generation_mode, rigging_options, source_model_url을 포함한다. 리깅 source GLB는 source_image_url에 넣지 않는다. 리깅 결과와 업로드 원본을 삭제할 때 다른 generation의 참조를 확인하고, MESH 결과를 리깅 원본으로 사용 중이면 원본 Storage 파일을 보존한다. 진행 중인 리깅 삭제는 취소 후 현재 row를 다시 읽어 완료와 취소의 경합도 처리한다.
