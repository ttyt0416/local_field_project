# 독립 리깅 worker

표준 라이브러리 HTTP 서버로 8190에서 실행한다. .runtime/token에 256-bit token을 생성하고 모든 endpoint에 Bearer 인증을 요구한다. /health는 checkpoint 파일·Qwen config와 시작 시 --check에서 확인한 CUDA·의존성 상태를 반환한다. /jobs/{UUID} POST는 원본 GLB와 temperature/num_beams를 받고, GET은 상태·queue_position, DELETE는 지정한 작업만 취소한다. /result GET은 완료 GLB를, /ack POST는 결과 저장 뒤 임시 input/output을 정리한다.

한 번에 하나의 GPU 추론 subprocess를 실행하며 최대 8개의 활성 작업을 수락한다. job.json은 임시 파일의 atomic replace로 보관하고 .runtime/jobs에서 재시작 시 queued를 복구하며 이전 processing은 중단 실패로 표시한다. 작업마다 별도 입력·출력·로그 폴더를 사용한다. 취소는 해당 process group만 종료한다. 결과는 backend의 Storage 저장 성공 전까지 보존한다. ComfyUI queue와 독립적이므로 GPU 사용량은 운영 시 함께 고려해야 한다.
