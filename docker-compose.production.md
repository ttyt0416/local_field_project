# Production 리깅 연결

AnimaDex 썸네일은 server의 ANIMADEX_DATA_DIR=/var/lib/local-field/animadex에 저장하며 호스트 .runtime/tag-catalogues/animadex를 bind mount한다. 컨테이너 재생성·이미지 rebuild 후에도 썸네일과 delta 상태를 보존한다. 가져오기는 docker compose exec -T server python -B -m app.animadex로 실행한다.

기존 production services와 포트는 유지한다. server는 호스트 SkinTokens worker의 8190 포트를 RIGGING_URL로 사용하고 rigging/.runtime/token을 읽기 전용 secret 파일로 mount한다. worker 설치·시작 후 token이 존재해야 한다. 변경한 web/server의 image 반영은 별도 배포 절차다. 자세한 실행 방법은 rigging/README.md와 docker-compose.md에 있다.

다운로드용 공용 토큰 파일을 서버 환경에 주입하지 않는다. Civitai와 Hugging Face 요청은 사용자가 다운로드 관리에 저장한 공용 토큰만 사용한다.

## 임베딩

Production 임베딩은 Qwen/Qwen3-Embedding-4B를 vLLM 0.33.0의 고정 이미지로 실행한다. 호스트 모델 경로는 /home/yoon/dev/models/Qwen3-Embedding-4B이며, 내부 주소는 http://embedding:30005이다. MRL을 활성화하고 출력 차원을 1024로 설정하여 기존 vector(1024) 스키마를 사용한다. 모델 변경 시 기존 태그 벡터 전체를 새 모델로 다시 생성한 뒤 서버 설정과 함께 전환해야 한다.

## 프롬프트 강화 LLM

생성 LLM은 호스트 30004의 vLLM 컨테이너에서 Qwen3.8-27B Fable Cold Fusion NVFP4를 사용한다. Production server는 LLM_MODEL=qwen3.8-27b-fable-nvfp4, LLM_VISION_ENABLED=true를 사용한다. 이미지·동영상·음악 강화는 공통 설정을 사용하며 영상 강화의 실제 이미지 미리보기를 분석한다. 영상·오디오 및 미래 continuation frame을 관찰했다고 주장하지 않는다. 영상 언어 제약은 native GBNF를 structured_outputs.grammar에 전달하고 다른 schema는 structured_outputs.json으로 전송한다. 사고 모드는 끈다.

Qwen3 임베딩 컨테이너와 1024차원 벡터는 기존 vLLM 런타임을 유지한다.

서빙 backend는 LLGuidance 기반 guidance로 명시 고정한다. auto 또는 XGrammar로 자동 선택하지 않는다.
