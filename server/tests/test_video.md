# MiniMax H3 동영상 계약 테스트

세 모드가 각각 올바른 workflow를 사용하고 `SaveVideo` dynamic combo payload를 구성하는지 확인한다. 선택 LoRA order, GPU allocator crash를 피하기 위한 Morton off 상태, PDD의 matching file·Euler sigma schedule·EasyCache exclusion, persisted continuation steps와 PDD state도 검증한다. video prompt enhancement는 strict `shots[]` object schema, server assembly, overall fields, server-side shot order non-revalidation을 검증한다. mode를 명시한 asset 해석과 기존 Storage asset 재사용도 검증한다. 테스트는 ComfyUI `/prompt`를 호출하지 않는다.
