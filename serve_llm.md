# 생성 LLM 실행

런처는 모델 디렉터리를 확인한 뒤 vLLM을 자식 프로세스 그룹으로 바로 시작한다. 시작 전 공유 RAM 잔량 검사와 대기, 실행 중 메모리 부족에 따른 자동 종료는 사용하지 않는다. 메모리 시작·실행 기준 환경 변수도 사용하지 않는다.

첫 CLI 인자에 있는 safetensors 파일만 POSIX_FADV_DONTNEED로 page cache 해제를 요청한다. 모델 health가 200이 된 뒤 같은 checkpoint 파일의 page cache 해제를 한 번 더 요청하며 GPU 가중치는 유지한다. 실제 해제량을 보장하는 값은 출력하지 않는다.

health는 LLM_HEALTH_URL(기본 http://127.0.0.1:30004/health)을 최대 10초마다 확인하고 성공 후 확인을 끝낸다. 이 확인은 로딩 후 page cache 해제 시점에만 사용하며 시작이나 실행을 제한하지 않는다.

Docker의 SIGTERM·SIGINT는 vLLM 프로세스 그룹으로 전달한다. 다른 서비스·생성 큐·모델 파일·전역 커널 캐시·swap 설정은 변경하지 않는다. source는 읽기 전용으로 mount한다.

Erebus NVFP4 텍스트 전용 사전 서빙의 가중치 메모리는 16.17GiB로 기록됐으며 본 서비스는 KV cache 4GiB를 사용한다.
