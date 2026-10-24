# Hugging Face 검증

네트워크와 운영 모델을 사용하지 않는 unittest다. 저장소·파일·폴더 URL과 encoded 리비전, 지원 확장자 필터, SHA/크기와 commit 고정, 외부 주소·경로 탈출 거부, CDN으로 토큰이 전달되지 않는지, 공개 파일의 무토큰 전송, 중복 저장 거부, Range 이어받기·전체 재전송·완료된 partial 재검증, 크기·SHA 오류, 작업별 partial 분리·중단을 합성 바이트로 확인한다.

`python -B -m unittest discover -s tests -p 'test_hugging_face.py'`로 실행한다. 별도 실제 연결 검증에서는 격리된 임시 컨테이너에서 hf-internal-testing/tiny-random-BertModel의 383481바이트 공개 파일을 다운로드·이어받기했으며 파일은 종료 시 제거했다.
