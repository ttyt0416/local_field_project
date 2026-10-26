# 콘텐츠 상세

콘텐츠 상세 페이지는 진입할 때마다 `GET /vault/images/{generation_id}`를 호출하고 서버에서 조회수를 증가시킨다. 이미지 결과의 파일 용량도 표시하며, 이미지 편집은 crop, 확대, 회전을 Canvas로 미리보고 원본을 보존한 새 콘텐츠를 저장한다. 초기 로딩 중에도 페이지 배경·뒤로가기·`콘텐츠 상세` 제목을 유지하고 실제 콘텐츠 영역만 `LoadingSpinner`로 표시한다. Storage signed URL 또는 인증 이미지 프록시로 결과 이미지를 표시하며, 무배경·무테두리 헤더에는 `콘텐츠 상세` 제목과 조회수만 표시한다. 완료 상태의 `IMAGE · 완료` 텍스트와 별도 타입 아이콘 container는 표시하지 않는다.

favorite 버튼은 제목 영역이 아니라 이미지 우측 하단에 배치하고, 테두리 없는 배경색 `filled` 아이콘 버튼을 사용한다. 다운로드 아이콘 버튼도 이미지 우측 하단에 함께 배치하며 favorite와 같은 primary 색상·디자인의 `filled` 버튼으로 표시하고 `GET /vault/images/{generation_id}/download`의 authenticated attachment response로 파일을 내려받는다. 버튼은 `PATCH /vault/images/{generation_id}/favorite`로 상태를 저장한다. 페이지 하단의 red 콘텐츠 삭제 버튼은 확인 모달을 연다. 확인 후 `DELETE /vault/images/{generation_id}`가 성공하면 browser history에 삭제된 detail route를 남기지 않도록 route replace로 `/vault`에 이동한다. 생성 파라미터에서는 family와 T2I/I2I mode를 표시하고 I2I 결과에는 denoise도 표시한다. 파일 경로는 표시하지 않으며 LoRA는 `이름 / strength` 형식으로 표시한다. 사용된 원문·개선된 긍정 prompt, 긍정·부정 prefix와 부정 prompt는 각각 label과 separate block으로 표시하며 긴 prompt와 prefix는 카드 너비 안에서 자동 줄바꿈한다. `이 설정으로 다시 생성`과 preset 저장은 네 값을 합치지 않고 동일한 separate fields로 전달한다. 제목 행은 `space-between`으로 배치하고 각각의 `Copy` 아이콘 버튼으로 클립보드에 복사한다. `이 설정으로 다시 생성`을 선택하면 family·mode·source file ID와 생성 설정을 `imageGenerationStore`에 저장하고 같은 T2I/I2I family 화면으로 이동한다. `이미지 편집`은 crop과 90도 단위 회전을 Canvas로 미리보고 원본을 보존한 새 콘텐츠를 저장한다. lightbox의 확대·축소 버튼은 100%·125% 단위로 최대 400%까지 표시 크기만 변경하며 파일 자체는 변경하지 않는다. 페이지 제목은 `콘텐츠 상세`이며 공용 `Typography`의 축소된 `display` variant를 사용한다. queued/processing image detail은 shared generation SSE store로 percent progress, queue position, elapsed time을 결과 media area와 생성 metadata에 표시한다.


다중 참조 이미지의 순서·파일명·소유자용 읽기 URL을 보여 주고, 재생성 요청에 reference_images를 그대로 전달한다. 제거한 Krea2 기록은 모델 옵션 요청과 재생성을 비활성화한다.

## MOSS

MOSS 기록의 moss 설정을 프리셋 저장과 재생성에 전달한다. 기존 이미지 참조 목록·소유권·원본 재사용 흐름을 유지한다.

Qwen 2.1 Turbo 결과는 qwen_image_2_1 family로 표시하고 원본·참조 순서와 파라미터를 복원해 I2I/R2I를 재실행할 수 있다.

이미지 기록의 prompt_enhancement_enabled를 프리셋과 재생성으로 전달한다.

Qwen 생성 상세에 LLM 프롬프트 강화 사용 여부를 표시한다.

공통 vLLM 개선 결과인 improved_prompt를 재생성 상태와 프리셋 초기값에 포함한다. 모든 이미지 family에서 원문과 개선 결과를 분리해 보존한다.
