Erebus 원본 Naphula/Erebus-RP-Engine-26B-A4B, revision 01b275a157bce01ce6415d66c271fd6eb49d3cc6을 이 GB10에서 NVFP4A16으로 변환한다. 공식 LLM Compressor model_free_ptq를 사용해 safetensors를 1 worker씩 읽고 변환한다. 전체 BF16 모델을 transformers로 한꺼번에 올리지 않는다. data-free RTN이므로 보정 데이터셋을 임의로 추가하지 않는다.

FP4 weights, BF16 activations이며 16개 단위 scale을 사용하는 nvfp4-pack-quantized 형식으로 저장한다. 임베딩·출력 head·라우터·비전·오디오 관련 모듈은 원래 BF16을 유지한다. Gemma 4 fused 3D expert는 공식 converter의 expert 분할을 사용한다. 원본 11개 shard의 공식 SHA-256 검증이 모두 있어야 시작한다.

시작 시 MemAvailable 40GiB 이상을 확인하며 실행 중 20GiB 미만이면 변환 프로세스를 종료한다. CUDA allocator는 전체 메모리의 15%로 제한한다. 변환 컨테이너도 CPU 메모리 24GiB로 제한한다. 다른 작업·서비스는 중지하지 않는다. 실패한 중간 결과는 완성 모델로 서빙하지 않는다.

사용 예 (정리된 BF16 원본은 고정 리비전으로 다시 다운로드하고 공식 SHA-256 검증 기록을 준비해야 한다):
```
docker build -f Dockerfile.quantize -t local-field-erebus-quantize:0.15.0 .
docker run --rm --gpus all --memory 24g --memory-swap 24g -v /home/yoon/dev/models:/models -v "$PWD/convert_erebus_nvfp4.py:/convert.py:ro" local-field-erebus-quantize:0.15.0 /convert.py /models/Erebus-RP-Engine-26B-A4B-BF16 /models/Erebus-RP-Engine-26B-A4B-NVFP4
```

변환 기록·원본 리비전·해시·도구 버전은 결과 모델 source_provenance.json에 남긴다. 참고: https://github.com/vllm-project/llm-compressor/blob/main/examples/model_free_ptq/README.md

완성 결과는 원본 구조에 맞는 정확히 11,520개 expert 행렬의 packed tensor와 BF16 비전·라우터·임베딩 보존을 확인한다. 결과 checkpoint의 로컬 SHA-256·파일 크기를 files에 기록하고, 공식 원본 해시 기록은 source_files로 분리한다. 로컬 변환 해시는 공식 다운로드 해시와 구분한다. 각 출력 hash 읽기 뒤 해당 파일 page cache만 해제를 요청한다.

Gemma 4의 post_feedforward_layernorm_1·_2처럼 norm으로 끝나지 않는 normalization도 명시적으로 제외한다. model-free의 자동 norm 제외만으로는 해당 1D weight가 Linear로 오인되므로 re:.*norm.*을 사용하여 원래 precision을 보존한다.

2026-11-16 실제 GB10 전체 변환은 416초에 완료됐으며 11개 shard·15.65GiB, packed 행렬 11,725개·expert 행렬 11,520개다. 원본에서 보존된 비전 tensor 5개는 전체 비전 지원을 의미하지 않는다. 원본은 vision encoder tensor 351개가 누락되어 있으며, 사용자 선택에 따라 외부 가중치 보완 없이 텍스트 전용으로 서빙한다. 원본 tokenizer·chat template를 유지한다.

source_provenance.json의 serving에도 사용자 선택에 따른 language_model_only=true, vision_enabled=false와 원본 누락 사유를 기록한다.
