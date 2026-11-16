생성 LLM은 사용자가 지정한 `esatapedico/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU-NVFP4`로 전환한다. 고정 리비전은 `2e9f861248c0087c16729e0606634c3c450808ae`이며 SHA-256 검증 결과는 모델 폴더의 source_provenance.json에 기록한다.

Strata 공식 모델 목록과 NVFP4 fork는 Qwen3.8-Flash-Next 등 MoE 계열을 지원하며 요청한 dense 27B checkpoint는 지원 대상으로 명시하지 않는다. 따라서 사용자가 지정한 fallback인 vLLM을 선택한다.

`docker-compose.llm.yml`의 generation-llm은 기존에 검증된 vLLM 0.33.0 ARM64 CUDA 13 고정 이미지로 GB10 SM121에서 실행한다. 모델은 compressed-tensors NVFP4 W4A16, group size 16, FP8 scales이며 비전·linear attention·lm_head·MTP head는 BF16으로 남아 있다. dtype BF16, 32768 context, 최대 동시 요청 2개, KV cache 4GiB, eager 실행으로 다른 GPU 작업과 메모리를 공유한다. NVFP4A16 커널은 설치된 vLLM의 SM121용 Marlin 선택을 확인했다.

API는 기존 30004 포트, served model name은 `qwen3.8-27b-fable-nvfp4`다. 모델 디렉터리는 읽기 전용이며 compilation·tokenizer cache는 .runtime/vllm에 둔다. 재시작 정책은 unless-stopped다. 사용자의 즉시 삭제 요청에 따라 기존 llama-server.service·llama.cpp 소스/빌드와 GLM Q6_K 모델 파일을 삭제했다.

구조화 출력 backend는 LLGuidance 1.7.6 기반 `guidance`로 명시 고정한다. auto/XGrammar를 선택하지 않는다. 영상 강화는 native GBNF를 `structured_outputs.grammar`에 전달하고 vLLM의 LLGuidance가 GBNF를 변환한다. 다른 이미지·음악 schema는 `structured_outputs.json`으로 전달한다. JSON 불필요한 공백과 사고 모드는 끄며 grammar는 reasoning 구간에도 적용한다. 각 요청도 enable_thinking=false, reasoning_effort=none을 사용한다.

Local Field 서버 기본 URL은 `http://host.docker.internal:30004`, LLM_MODEL은 위 alias, LLM_VISION_ENABLED는 true다. 영상 강화의 선택 이미지 preview를 label과 함께 전달한다. 영상·오디오의 실제 내용, 아직 생성되지 않은 continuation frame은 관찰했다고 주장하지 않는다. 공식 H3 영어 설명과 원문 대사·가사·화면 글자 보존은 영역별 GBNF와 서버 재검증으로 적용한다.

Qwen3-Embedding-4B는 기존 별도 vLLM 컨테이너의 30005 포트·1024차원을 유지한다. 임베딩·태그 벡터·관련 DB는 이 전환에 포함하지 않는다.

검증: 삭제 전 서버 검증 331개(2개 생략), Svelte 검사 오류·경고 0개, 참조 preview 테스트를 통과했다. Native GBNF와 요청 Qwen tokenizer를 사용하는 LLGuidance에서 정상 원문·Unicode 우회·장면/참조 위반 18개 사례를 모두 확인했으며 167토큰의 실제 마스크 계산도 통과했다. 새 모델의 실제 API에서도 native GBNF 영어 제한·한국어 원문 보존, 비전의 빨간 배경/파란 원 인식과 JSON schema 응답을 확인했다. 배포된 영상 강화 API의 I2V 한국어 대사·중국어 화면 글자 보존(38.28초), FL2V 이미지 2개·6.58초 공식 접두문(19.45초), R2V 6개 섹션·Subject 정의·task enum·선택된 참조 label(38.32초)을 모두 통과했다. 재로딩 뒤 신규 커널 OOM은 없었다.

```bash
docker compose -f docker-compose.llm.yml up -d generation-llm
docker compose -f docker-compose.llm.yml logs --tail 100 generation-llm
```

공식 참고:
- https://github.com/thread3d/strata/blob/main/docs/MODELS.md
- https://github.com/sergqwer/strata-nvfp4
- https://github.com/vllm-project/recipes/blob/main/models/Qwen/Qwen3.8-27B.yaml
- https://github.com/guidance-ai/llguidance/blob/main/python/llguidance/_grammar_from.py

모델은 huggingface_hub의 실제 hf_xet 경로로 받으며 고성능 Xet 전송을 사용한다. 공식 LFS SHA-256: 첫 샤드 3087d4e2bbbdbac39178eda4ddf53e689843fab837aa6bf9236c7f8b41ea0c1b, 두 번째 b1ffe20c9663fec32a7acf74780d05a8c418bc763311cc07dc28f861dda6ffff.

사용자 요청으로 기존 server/tests·web/tests를 모두 삭제했다. 위 검증은 삭제 전에 완료했다. 임시 검증 파일과 다운로드 중간 파일·캐시는 작업 완료 시 제거한다.

GB10 공유 RAM에서 SHA-256 검사 후 모델 page cache 때문에 CUDA context 초기화 OOM이 확인됐다. serve_llm.py가 해당 모델 파일의 page cache 해제를 요청한 후 MemAvailable 70GiB 이상일 때만 vLLM을 시작한다. 실행 중 여유가 12GiB 미만이면 생성 LLM을 종료하고, 재시작은 시작 기준을 만족할 때까지 대기한다. 2026-11-16 로딩 중 메모리 고갈로 ChatGPT 앱이 OOM 종료된 사실을 반영한 보호 장치다. 호스트는 재부팅되지 않았다. 전역 cache·swap·다른 GPU 서비스 설정은 변경하지 않는다.

시작 전과 health 성공 후 모델 checkpoint page cache만 해제를 요청한다. 실제 로딩 후 정리로 MemFree가 약 4GiB에서 30GiB로 증가했으며, GPU 가중치와 서비스는 유지됐다.
