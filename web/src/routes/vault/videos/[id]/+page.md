# 동영상 콘텐츠 상세

동영상 보관함의 설명 링크는 `/vault/videos/{id}`로 이동하고 상세 API 진입 시 조회수를 증가시킨다. 상세 페이지는 동영상, 생성 방식, FPS, 상태, 생성 시각, 분·초 형식의 재생 시간, 파일 용량, 소요 시간, 조회수와 favorite 상태를 표시한다. LTX generation은 checkpoint 아래에 저장된 LoRA name·strength 목록도 표시하고, `프리셋 저장`은 같은 목록을 video preset initial value에 전달한다. native player controls와 겹치지 않도록 다운로드와 favorite filled icon button은 player 우측 하단보다 위에 배치한다. 상세 prompt 영역은 스타일·전체 배경 다음에 저장된 입력 프롬프트와 개선 프롬프트를 각 segment별 순서로 표시한다. page, grid, card, prompt block은 `w-full min-w-0 max-w-full` constraints를 가지며 long unspaced prompt tokens는 `break-words`로 wrap해 horizontal overflow를 만들지 않는다.

`동영상 편집`은 시작·종료 시간, crop 좌표, 90도 단위 회전을 입력받아 `POST /vault/videos/{generation_id}/edit`에서 FFmpeg로 새 MP4를 저장한다. 원본은 보존하고 편집 결과 상세에는 `편집 결과` badge를 표시한다. 기존 결과에 저장된 용량이 없으면 상세 조회에서 Storage metadata를 보완한다.
