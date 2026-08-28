# MiniMax H3 동영상 생성

`POST /generation/video/{mode}`는 `i2v`, `fl2v`, `r2v`를 각각 독립 workflow로 실행한다. R2V는 reference 이미지·동영상·오디오를 받으며, 동영상은 ComfyUI에서 프레임과 paired audio로 분리한다. 선택된 기존 Storage 파일은 소유권을 확인해 재사용하고, 새 이미지·동영상·오디오는 이 요청이 실제로 시작될 때만 Storage에 업로드한다. 선택만 하거나 미리보기만 하는 동작은 업로드·DB 생성·ComfyUI queue 제출을 수행하지 않는다.

I2V와 FL2V는 `fl2va` 모델을 사용하고 R2V는 `ref2va` 모델과 R2V 전용 4-step LoRA를 사용한다. ComfyUI 입력 파일은 생성 요청 중에만 임시 입력으로 업로드한다. 생성 요청은 ComfyUI `/prompt` 제출과 DB active row 생성을 완료한 뒤 `202`를 반환한다. 이후 서버 `generation_worker.py`가 브라우저와 독립적으로 `queued`·`processing` 작업을 확인하고, ComfyUI history 완료 시 결과를 Storage에 저장하고 DB를 갱신한다. 프런트는 `GET /generation/video/{mode}/{prompt_id}/events` SSE에서 최초 DB snapshot 이후 worker가 publish한 상태·완료·실패 이벤트를 받으며, 화면을 떠나면 SSE 연결만 종료되고 서버 작업은 계속된다.

`VideoAsset`의 `file_id`는 기존 재사용 콘텐츠이고 `file_index`는 이번 multipart 요청의 새 파일이다. 새 파일과 기존 파일은 소유자 검증·형식 검증·크기 제한을 동일하게 적용한다.
