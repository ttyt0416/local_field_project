# T2I 생성 페이지

페이지 URL은 `/generate/image`이며 `family` 쿼리를 사용하지 않는다. 초기 모델은 `imageGenerationStore.pending.model_family`의 재생성 설정에서 선택하고, 설정이 없으면 Anima를 사용한다. 이후 모델 탭은 로컬 상태만 변경하고 {#key modelFamily}에 해당하는 생성 컴포넌트를 조건부로 다시 렌더링한다. 탭 클릭으로 라우트나 페이지를 다시 열지 않는다. 생성 컴포넌트가 재생성 설정을 소비하기 전에 페이지가 모델을 선택하므로 Illustrious·MOSS 재생성도 같은 URL에서 해당 모델로 열린다.

세부 생성·프리셋·결과 처리는 web/components/generation/text-to-image-generator.svelte에서 담당한다.
