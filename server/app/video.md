# MiniMax H3 동영상 생성

`POST /generation/video/{mode}`는 `i2v`, `fl2v`, `r2v`를 각각 독립 workflow로 실행한다. 선택된 기존 Storage 파일은 소유권을 확인해 재사용하고, 새 이미지·오디오는 이 요청이 실제로 시작될 때만 Storage에 업로드한다. 선택만 하거나 미리보기만 하는 동작은 업로드·DB 생성·ComfyUI queue 제출을 수행하지 않는다.

I2V와 FL2V는 `fl2va` 모델을 사용하고 R2V는 `ref2va` 모델과 R2V 전용 4-step LoRA를 사용한다. ComfyUI 입력 파일은 생성 요청 중에만 임시 입력으로 업로드한다. 생성 결과는 history에서 확인한 뒤 Storage에 저장하고, 사용자 소유 영상 generation과 연결한다.

`VideoAsset`의 `file_id`는 기존 재사용 콘텐츠이고 `file_index`는 이번 multipart 요청의 새 파일이다. 새 파일과 기존 파일은 소유자 검증·형식 검증·크기 제한을 동일하게 적용한다.
