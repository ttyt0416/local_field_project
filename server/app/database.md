# 이미지 Storage 메타데이터

`image_generations.storage_file_id`는 실제 이미지 바이트를 저장하지 않고 독립 Storage 서비스의 파일 식별자만 보관한다.

기존 데이터베이스에는 시작 시 migration statement가 nullable 컬럼을 추가한다. 기존 `file_path`, `filename`, `subfolder`, `image_type` 값과 기존 이미지 프록시 fallback은 유지한다.
