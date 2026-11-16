# 생성 LLM 시작과 공유 RAM 보호

GB10은 GPU와 시스템 RAM을 공유한다. 모델 다운로드·SHA-256 검증으로 safetensors page cache가 남은 상태에서 CUDA context 초기화가 OOM으로 실패했다. 해당 파일 캐시 해제 전 free RAM은 18GiB, 해제 후 44GiB였다. 캐시 해제만으로 로딩 중 메모리 압박까지 막을 수는 없다.

2026-11-16 10:37 JST에는 Qwen 로딩과 다른 GPU 모델의 메모리가 겹쳐 RAM·swap이 고갈됐고, 커널 OOM killer가 ChatGPT 앱을 종료했다. 호스트 재부팅은 없었다. Qwen 자체는 이후 로딩을 완료했으며 가중치 할당은 26.06GiB로 기록됐다.

런처는 첫 CLI 인자에 있는 safetensors 파일만 POSIX_FADV_DONTNEED로 캐시 해제를 요청한다. 실제 해제량을 보장하는 값은 출력하지 않는다. MemAvailable이 70GiB 이상일 때 vLLM을 자식 프로세스 그룹으로 시작한다. 부족하면 15초마다 확인하며 대기한다. 이 시작 기준은 약 26.6GiB checkpoint·26.06GiB GPU 가중치·변환 중간 버퍼와 시스템 여유를 고려한 보수적 값이다.

실행 중에도 1초마다 MemAvailable을 확인한다. 12GiB 미만이면 생성 LLM 그룹에 SIGTERM을 보내고 최대 5초 뒤에도 남으면 SIGKILL로 종료한다. Docker 재시작 시 시작 기준을 다시 만족할 때까지 대기한다. LLM_MIN_START_AVAILABLE_GIB·LLM_MIN_RUNNING_AVAILABLE_GIB로 기준을 명시할 수 있다. 이는 메모리 급증의 모든 경우를 보장하는 하드 메모리 제한은 아니다.

Docker의 종료 신호는 vLLM 그룹으로 전달한다. 다른 서비스·생성 큐·모델 파일·전역 커널 캐시·swap 설정은 변경하지 않는다. source는 읽기 전용으로 mount한다.

모델 health가 200이 된 후에는 같은 checkpoint 파일의 page cache 해제를 한 번 더 요청한다. 로딩 완료 뒤 남는 CPU 파일 캐시를 정리하는 용도이며 GPU 가중치는 유지한다. health는 LLM_HEALTH_URL(기본 http://127.0.0.1:30004/health)을 최대 10초마다 확인하고, 성공 후 확인을 끝낸다. 실제 로딩 후 해제로 MemFree가 약 4GiB에서 30GiB로 증가했다.
