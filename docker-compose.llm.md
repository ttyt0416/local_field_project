생성 LLM은 사용자가 지정한 Naphula/Erebus-RP-Engine-26B-A4B다. 원본 고정 리비전은 01b275a157bce01ce6415d66c271fd6eb49d3cc6이며 11개 BF16 checkpoint는 48.46GiB다. 실제 hf_xet 다운로드와 11개 공식 LFS SHA-256 대조를 완료했다. 모델 폴더의 source_provenance.json은 원본 해시를 source_files에, 로컬 변환 해시를 files에 구분해 보존한다.

사용자 요청으로 이 GB10에서 공식 LLM Compressor model_free_ptq로 NVFP4A16을 직접 생성했다. FP4 weights·BF16 activations·16개 단위 scales를 사용하는 nvfp4-pack-quantized다. 변환 도구는 Dockerfile.quantize의 LLM Compressor 0.15.0·compressed-tensors 0.20.1로 분리한다. 보정 데이터 없는 RTN이며 전체 BF16 모델을 한 번에 GPU에 올리지 않는다. 임베딩·lm_head·라우터·비전·오디오·normalization은 원래 precision을 유지한다. 변환 결과는 11개 shard·15.65GiB, 총 11,725개 packed 행렬 중 expert 행렬 11,520개다. packed uint8·FP8 group scales·FP32 global scales 및 출력 전체 index와 로컬 해시를 확인했다.

원본 config는 Gemma4ForConditionalGeneration, 30 text layers·128 experts·top-8 routing이다. 그러나 원본 checkpoint에는 vision encoder 가중치 351개가 없고 비전 관련 tensor 5개만 존재한다. 사용자는 다른 기반 모델의 비전 가중치를 보완하지 않고 Erebus 원본을 텍스트 전용으로 쓰도록 선택했다. --language-model-only를 명시하며 이미지·영상·음악의 텍스트 프롬프트 강화는 유지한다. 참조 이미지 자체를 분석하지 않고 입력 설명과 참조 label만 사용한다. Erebus tokenizer·chat template를 유지하며 외부 모델의 비전 가중치나 processor를 추가하지 않는다.

서빙은 vLLM 0.33.0 ARM64 CUDA 13 고정 digest를 사용한다. 별도 변환 이미지의 패키지는 서빙 이미지에 설치하지 않는다. 실제 GB10에서 MarlinNvFp4LinearKernel·MarlinExperts와 TRITON_ATTN을 선택했다. served model name은 erebus-rp-engine-26b-a4b-nvfp4, 포트는 30004다. Gemma 4 reasoning parser, thinking 비활성화, BF16 dtype, 32768 context, 동시 요청 2개, KV cache 4GiB, eager 실행을 사용한다.

구조화 출력은 LLGuidance 1.7.6 기반 guidance로 고정한다. auto/XGrammar를 선택하지 않는다. 영상 강화는 native GBNF를 structured_outputs.grammar에 전달한다. 선택한 한국어·영어·일본어 집합을 설명 문자 범위에 적용하고 대사·가사·화면 글자는 원문을 보존한다. 고정 H3 protocol·참조 label·task enum은 유지한다. 일반 이미지·음악 강화는 공통 클라이언트의 structured_outputs.json을 사용한다. enable_thinking=false, reasoning_effort=none이며 grammar는 reasoning 구간에도 적용한다.

Local Field 서버 기본 URL은 http://host.docker.internal:30004, LLM_MODEL은 위 alias, LLM_VISION_ENABLED는 false다. 임베딩은 별도 Qwen3-Embedding-4B vLLM의 30005 포트·1024차원을 유지한다.

GB10은 CPU·GPU RAM을 공유한다. serve_llm.py는 시작 전과 health 성공 뒤 해당 checkpoint page cache만 해제를 요청한다. MemAvailable 70GiB 이상일 때 시작하고 실행 중 12GiB 미만이면 생성 LLM을 종료한다. 재시작도 시작 기준을 다시 확인한다. 이는 모든 순간의 메모리 급증을 보장하는 하드 제한은 아니다. 2026-11-16 이전 Qwen 로딩 시 RAM·swap 고갈로 ChatGPT 앱이 OOM 종료된 기록을 반영한 보호다. 호스트 재부팅은 없었다.

이전 Qwen3.8 생성 컨테이너와 가중치는 중지·삭제했다. llama.cpp·GLM도 앞선 요청으로 삭제됐으며 복구하지 않는다. 기존 server/tests·web/tests 삭제 요청을 유지하고 검증은 임시 stdin·컨테이너로 수행한다. 교체 검증 뒤 BF16 원본·임시 검증 파일·다운로드와 실행 캐시·임시 변환 이미지를 정리했다. 완성 NVFP4와 provenance는 보존한다.

검증: Svelte 오류·경고 0개, 브라우저 언어 선택과 최소 1개 선택 동작을 확인했다. 실제 Erebus tokenizer·LLGuidance에서 선택 언어·비선택 문자·잘못된 참조·원문 보존 12개 사례가 통과했다. 변환본을 vLLM에 실제 로드하고 JSON schema 응답, reasoning 미노출, 한국어·영어·일본어 native GBNF 생성을 확인했다. 본 서비스에서 KO I2V·JA FL2V·EN R2V 실제 강화, 원문 한국어 대사와 중국어 화면 글자 보존, 6.5초 입력의 6.58초 프레임 정합, R2V 여섯 섹션·Subject 정의, 이미지·음악 공통 강화 API가 모두 통과했다. 서버의 실제 설정도 Erebus alias·vision=false로 확인했다.

실행:
```
docker compose -f docker-compose.llm.yml up -d generation-llm
docker compose -f docker-compose.llm.yml logs --tail 100 generation-llm
```

참고:
- https://huggingface.co/Naphula/Erebus-RP-Engine-26B-A4B
- https://github.com/vllm-project/llm-compressor/blob/main/examples/model_free_ptq/README.md
- https://github.com/vllm-project/llm-compressor/blob/main/examples/quantization_w4a16_fp4/nvfp4/gemma4_example.py
- https://docs.vllm.ai/projects/recipes/en/stable/Google/Gemma4.html
