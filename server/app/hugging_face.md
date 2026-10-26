# Hugging Face 모델 다운로드

모델 저장소 ID·저장소 URL·tree 폴더 URL·blob/resolve 파일 URL을 받는다. 모델 저장소만 지원하고 datasets·spaces 경로는 받지 않는다. 리비전 입력이 비어 있으면 URL의 리비전 또는 main을 사용한다. slash가 있는 리비전은 URL에서 percent encoding으로 구분한다.

공식 Hub API `GET /api/models/{repo_id}/revision/{revision}?blobs=true`로 지원되는 모델 파일의 경로·바이트 크기·LFS SHA-256을 조회한다. JSON 응답은 16MiB로 제한하고 경로 탈출·제어문자·부적합 이름을 거부한다. 조회 결과의 40자 commit SHA를 이후 enqueue와 worker에 고정하므로 branch가 바뀌어도 같은 파일을 받는다. 조회된 repo·commit·filename으로만 resolve URL을 다시 구성한다.

네트워크 요청은 HTTPS Hugging Face 도메인과 공식 hf.co/huggingface.co 하위 CDN만 허용하고 최대 다섯 번의 리디렉션을 따른다. 토큰은 huggingface.co 요청에만 보내고 CDN에는 보내지 않는다. 서명 URL과 토큰은 응답·다운로드 작업 기록·오류 메시지에 저장하지 않는다. 공개 저장소는 토큰 없이 사용하며 제한·비공개 저장소는 개인 계정에 저장한 토큰과 저장소 접근 승인이 필요하다. 접근 승인을 자동으로 처리하지 않는다.

기준: [공식 API 클라이언트의 model_info](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/hf_api.py), [공식 다운로드/CDN 문서](https://huggingface.co/docs/hub/models-downloading).

토큰은 다운로드 관리에서 사용자별 저장이 가능하며 제한 모델 오류는 해당 화면의 API 토큰과 저장소 접근 승인을 안내한다.

## 동작·오류 기록

실패 HTTP 응답은 기록 스레드에서 원문을 읽고 닫도록 보존한다. 정상 리디렉션 응답은 즉시 닫는다.
