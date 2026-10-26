# SkinTokens API 연결

`GET /generation/3d/rigging/options`는 worker 모델·CUDA readiness와 Storage 준비 상태를 확인한다. `POST /generation/3d/rigging`는 multipart payload(temperature, num_beams, optional source_generation_id)와 optional file(GLB)을 받는다. 입력은 파일 또는 현재 사용자 소유의 완료된 MESH generation 중 하나다. GLB 2.0 헤더·실제 길이·200 MiB 제한을 검사한다.

입력 GLB는 Storage에 저장하고 기존 three_d_generations에 generation_mode=rigging row를 만든다. 독립 worker에는 파일 바이트와 서버가 만든 UUID만 전달하며 브라우저에는 worker token이나 파일 경로를 노출하지 않는다. RIGGING_URL 기본값은 http://host.docker.internal:8190, RIGGING_TOKEN_FILE 기본값은 /run/secrets/rigging_token이다. 파일 전송과 source 다운로드는 thread로 실행한다.

worker 상태는 기존 3D reconciler·조회·SSE에서 동기화하며 완료 GLB를 Storage에 보관한 뒤 worker에 ack하여 임시 바이트를 정리한다. 완료된 row는 worker가 없어도 조회할 수 있다. 단일 backend process 내 lock으로 중복 저장과 완료·취소 경합을 막는다. 현재 backend 배포는 단일 uvicorn process다. 수평 확장 시 DB claim이 추가로 필요하다.

호스트 worker 연결은 인증된 내부 API다. worker 요청은 기존 audit DB에, 실행 실패는 error DB와 generation error_message에 남긴다. 다른 사용자 generation ID를 통한 source 접근은 거부한다.

## 동작·오류 기록

자격 파일·HTTP·네트워크·JSON 예외를 원문 유틸로 보존한다. 시작 실패 상태에 원인 문구를 저장하며 원격 실패 응답 전체도 기록한다. ack 실패는 request_worker에서 기록한다.
