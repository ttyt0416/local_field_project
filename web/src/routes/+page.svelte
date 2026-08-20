<script lang="ts">
	import { APP_NAME, SERVER_DOCS_URL } from '$lib/configs/constants';
</script>

<svelte:head>
	<title>{APP_NAME}</title>
	<meta
		name="description"
		content="로컬 AI 미디어 생성 시스템을 제어하고 관리하는 Local Field"
	/>
</svelte:head>

<main>
	<p class="eyebrow">LOCAL FIELD</p>
	<h1>AI 미디어 생성 시스템을 한곳에서 관리합니다.</h1>
	<p class="description">
		로컬 환경의 이미지·영상·음성·3D 생성 시스템을 연결하고 생성 작업과 결과물을 관리합니다.
	</p>
	<a href={SERVER_DOCS_URL}>FastAPI API 문서 열기</a>
</main>

<style>
	:global(*) {
		box-sizing: border-box;
	}

	:global(body) {
		margin: 0;
		background: #101113;
		color: #f4f4f5;
		font-family:
			Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
	}

	main {
		min-height: 100vh;
		max-width: 960px;
		margin: 0 auto;
		padding: 12rem 2rem;
	}

	.eyebrow {
		margin: 0 0 1.5rem;
		color: #8b5cf6;
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.2em;
	}

	h1 {
		max-width: 720px;
		margin: 0;
		font-size: clamp(2.5rem, 7vw, 5.5rem);
		line-height: 0.98;
		letter-spacing: -0.06em;
	}

	.description {
		max-width: 560px;
		margin: 2rem 0 1.5rem;
		color: #a1a1aa;
		font-size: 1.1rem;
		line-height: 1.7;
	}

	a {
		color: #c4b5fd;
		font-weight: 700;
	}
</style>
