# 다운로드 종류 추정 검증

`node --experimental-strip-types tests/model-type.test.ts`로 실행한다. 실제 Hugging Face에서 사용하는 split_files·UNet·transformer·text_encoder 경로, GGUF, 파일명과 저장소 계열이 충돌할 때 파일 정보 우선, 알려진 단서가 없을 때 null 반환을 검증한다. 실제 네트워크 요청이나 모델 다운로드는 실행하지 않는다.
