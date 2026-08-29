# MiniMax H3 동영상 생성

`POST /generation/video/{mode}`는 `i2v`, `fl2v`, `r2v`를 각각 독립 workflow로 실행한다. R2V는 참조 이미지·동영상·오디오를 받으며, 동영상은 ComfyUI에서 프레임과 paired audio로 분리한다. 선택된 기존 Storage 파일은 소유권을 확인해 재사용하고, 새 이미지·동영상·오디오는 이 요청이 실제로 시작될 때만 Storage에 업로드한다. 선택만 하거나 미리보기만 하는 동작은 업로드·DB 생성·ComfyUI queue 제출을 수행하지 않는다.

I2V와 FL2V는 `fl2va` 모델을 사용하고 R2V는 `ref2va` 모델과 R2V 전용 4-step LoRA를 사용한다. ComfyUI 입력 파일은 생성 요청 중에만 임시 입력으로 업로드한다. 생성 요청은 ComfyUI `/prompt` 제출과 DB active row 생성을 완료한 뒤 `202`를 반환한다. 이후 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업을 확인하고, ComfyUI history 완료 시 결과를 Storage에 저장하고 DB를 갱신한다. 프런트는 `GET /generation/video/{mode}/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트를 받으며, 화면을 떠나면 SSE 연결만 종료되고 서버 작업은 계속된다.

`VideoAsset`의 `file_id`는 기존 재사용 콘텐츠이고 `file_index`는 이번 multipart 요청의 새 파일이다. 새 파일과 기존 파일은 소유자 검증·형식 검증·크기 제한을 동일하게 적용한다.

`POST /generation/video/enhance-prompt`는 이미지 생성과 같은 vLLM 기반 prompt 개선 endpoint다. vLLM은 AtlasCloud의 MiniMax H3 규칙을 우선해 `style`, `timeline`, `camera`, `audio`, `text`, `negative` 문자열 필드를 가진 JSON만 반환한다. 서버는 이 필드를 `Style`, `Timeline`, `Camera`, `Audio`, `Text`, `Negative` 6블록으로 순서대로 조립하며, Timeline은 선택한 duration 전체를 다루고 camera·audio·화면 text·negative 제약을 명시한다. 조립된 prompt에는 video submit 시 실제 참조 입력의 역할을 `@imageN`, `@videoN`, `@audioN`으로 앞에 붙인다.

`prompt_output_languages`는 `ko`, `en`, `ja` 중 1개 이상을 받는 multi-select 필드다. 개선 결과는 선택 언어의 문자 집합 union과 숫자·ASCII 특수기호·공백·줄바꿈만 허용하는 JSON schema pattern과 서버 검증을 모두 통과해야 한다. 개선이 활성화된 생성 요청도 같은 6블록·문자 규칙을 다시 검증하며, 개선 결과가 없거나 규칙을 벗어나면 queue 제출과 입력 업로드 전에 `422`로 거절한다.
