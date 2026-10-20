# I2I 생성 페이지

초기 family는 URL 쿼리로 선택한다. 이후 모델 탭은 로컬 상태만 변경하고 {#key family}에 해당하는 생성 컴포넌트를 조건부로 다시 렌더링한다. 탭 클릭으로 라우트나 페이지를 다시 열지 않는다. URL을 통한 직접 진입·Vault 재생성은 유지한다.

세부 생성·프리셋·결과 처리는 web/components/generation/image-to-image-generator.svelte에서 담당한다.
