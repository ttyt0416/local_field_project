<script lang="ts">
	import { browser } from '$app/environment';
	import LoadingShimmer from '../loadings/loading-shimmer.svelte';

	type MediaSource = string | Blob;
	type ModelViewerElement = HTMLElement & {
		cameraControls?: boolean;
		autoRotate?: boolean;
	};
	type Props = {
		source: MediaSource;
		alt?: string;
		sourceType?: 'local' | 'server';
		cameraControls?: boolean;
		autoRotate?: boolean;
		poster?: string;
		shadowIntensity?: number;
		exposure?: number;
		class?: string;
	};

	let {
		source,
		alt = '3D 모델',
		sourceType = 'local',
		cameraControls = true,
		autoRotate = false,
		poster,
		shadowIntensity = 1,
		exposure = 1,
		class: className = ''
	}: Props = $props();

	let sourceUrl = $state('');
	let loaded = $state(false);
	let failed = $state(false);
	let modelViewer = $state<ModelViewerElement>();
	const modelViewerTag = 'model-viewer';
	let isServerSource = $derived(sourceType === 'server' || (typeof source === 'string' && /^(https?:)?\/\//.test(source)));

	$effect(() => {
		if (browser) void import('@google/model-viewer');
	});

	$effect(() => {
		loaded = false;
		failed = false;
		if (typeof source === 'string') {
			sourceUrl = source;
			return;
		}
		if (!browser) {
			sourceUrl = '';
			return;
		}
		const objectUrl = URL.createObjectURL(source);
		sourceUrl = objectUrl;
		return () => URL.revokeObjectURL(objectUrl);
	});

	$effect(() => {
		if (!modelViewer) return;
		modelViewer.cameraControls = cameraControls;
		modelViewer.autoRotate = autoRotate;
	});
</script>

<div class={`relative overflow-hidden rounded-xl bg-muted ${className}`}>
	{#if isServerSource && !loaded && !failed}
		<LoadingShimmer class="absolute inset-0 z-10 h-full w-full rounded-none" label="3D 모델 불러오는 중" />
	{/if}

	{#if failed}
		<div class="flex min-h-64 items-center justify-center px-4 text-center text-sm text-muted-foreground" role="alert">
			3D 모델을 불러올 수 없습니다.
		</div>
	{:else}
		<svelte:element
			this={modelViewerTag}
			bind:this={modelViewer}
			src={sourceUrl}
			alt={alt}
			poster={poster}
			camera-controls={cameraControls ? '' : undefined}
			auto-rotate={autoRotate ? '' : undefined}
			interaction-prompt="auto"
			shadow-intensity={shadowIntensity}
			exposure={exposure}
			loading="lazy"
			onload={() => (loaded = true)}
			onerror={() => (failed = true)}
			class={`block h-full min-h-64 w-full bg-muted transition-opacity ${isServerSource && !loaded ? 'opacity-0' : 'opacity-100'}`}
		></svelte:element>
	{/if}
</div>
