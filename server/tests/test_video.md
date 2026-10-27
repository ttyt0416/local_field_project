# MiniMax H3 동영상 계약 테스트

세 모드가 각각 올바른 workflow를 사용하고 `SaveVideo` dynamic combo payload를 구성하는지 확인한다. 체크포인트는 MiniMaxH3 폴더의 임의 이름과 중첩 폴더를 허용하고 외부·미설치 경로는 제외하는지 검증한다. 특정 기본 파일 없이 설치된 첫 경로를 사용하며 명시한 steps를 보존한다. 선택 LoRA order, GPU allocator crash를 피하기 위한 Morton off 상태, PDD의 matching file·Euler sigma schedule·EasyCache exclusion, persisted continuation steps와 PDD state도 검증한다. video prompt enhancement는 empty overall plus nonempty segment request, `temperature=0.6`, 설명문 언어 선택과 원문 대사 보존 지시, removed MiniMax expert-role sentence, mode별 strict `shots[]` object schema, server assembly, overall fields를 검증한다. Shot-level exact `N/A` placeholder는 final shot line에서 제외하고 top-level sound fields의 `N/A`는 유지하는 contract도 검증한다. missing physics detail과 character별 expression and action을 요구하는지도 확인한다. mode를 명시한 asset 해석과 기존 Storage asset 재사용도 검증한다. 테스트는 ComfyUI `/prompt`를 호출하지 않는다.

명시적 scenes 배열과 기존 heading 입력 모두 정확한 샷 수를 schema에 강제하는지 확인한다. 세 모드의 1초 구간에서도 세 장면이 각각 Shot 1·2·3으로 조립되고 순서를 보존하는지 검증한다. 장면 수 불일치, scene_id 누락·중복·역순, 첫 시각 오류·역행·중복·구간 밖 시각을 거부하며 endpoint가 503과 오류 객체를 audit에 전달하는지 검사한다. scenes의 빈 항목·개수·길이 제한, 공백 정리, 배열과 heading의 중복 계산 방지도 확인한다.

첫 샷 동작 보존, 영어 설명과 한국어 대사·화면 글자 혼합, 행동·대사에 배분한 field별 길이, 장면 수·언어·R2V에 따른 token budget, labeled image 전달, 잘못된 미리보기 거부, FL2V 종료 시간, R2V 6개 section과 일반 참조 header 중복 방지를 회귀 검사한다.
