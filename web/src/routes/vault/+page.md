# Vault 콘텐츠 목록 표시

Vault API는 Storage signed URL이 있는 이미지에는 external URL을, Local Field가 반환한 relative path에는 authenticated Blob load를 사용한다. 목록은 latest·oldest·most viewed 정렬과 server-side search, page size 10 pagination을 제공한다.

각 image card는 type·status·created time·prompt·checkpoint·elapsed·view count와 download/favorite/delete actions를 표시한다. image와 video download action은 signed Storage URL을 browser에서 직접 fetch하지 않고, owner-scoped `GET /vault/images/{generation_id}/download`와 `GET /vault/videos/{generation_id}/download` attachment response로 파일을 내려받는다. detail link는 `/vault/images/{generation_id}`다. image/video/3D card는 shared generation SSE store로 queued/processing state를 media area와 metadata에 표시한다. image/video는 percent progress, queue position, elapsed time을, 3D는 생성 페이지와 같은 actual stage, queue position, elapsed time을 표시한다. video와 3D tab은 기존 category와 pagination behavior를 유지한다.

단일 image/video/3D 삭제와 선택 image 삭제가 성공하면 현재 filter와 page로 list API를 다시 호출해 items, completed count, total count, total pages를 server response로 갱신한다. 삭제 후 현재 page가 새 total pages를 벗어나면 마지막 유효 page를 다시 요청한다. Filter 전체 삭제는 page 1을 다시 요청한다.

FLUX 3 Klein 편집은 `model_family="flux3_klein"`, `generation_mode="i2i"`, `i2i_flux3_klein` preset namespace로 구분한다. 신규 family 선택에서 Krea2는 제거하며 이전 생성 데이터는 유지한다.

MOSS 분류는 T2I 전용이며 선택 시 I2I 방식 탭을 표시하지 않는다.

Qwen 2.1 Turbo 분류는 I2I/R2I 전용이므로 T2I 방식 탭을 표시하지 않는다.

3D 카드에 MESH와 RIGGING을 구분해 표시한다. RIGGING 카드에는 메시 생성용 프리셋·Seed 대신 SkinTokens 자동 리깅을 표시하며, 리깅 모델 로딩·뼈대 생성·스킨 가중치 단계를 표시한다.

완료된 RIGGING 카드에는 원본 이미지 대신 공용 ModelViewer로 실제 리깅 GLB를 표시한다. 인증된 모델 API를 사용하며 목록에서 회전·확대할 수 있다. 생성 중인 작업은 진행 상태를 우선 표시하고, MESH 카드의 소스 이미지 표시 방식은 유지한다.
