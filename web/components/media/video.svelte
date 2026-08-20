<script lang="ts">
	import { browser } from '$app/environment';
	import LoadingShimmer from '../loadings/loading-shimmer.svelte';

	type MediaSource = string | Blob;
	type Props = {
		source: MediaSource;
		sourceType?: 'local' | 'server';
		preview?: boolean;
		previewSeconds?: number;
		controls?: boolean;
		muted?: boolean;
		class?: string;
	};

	let {
		source,
		sourceType = 'local',
		preview = true,
		previewSeconds = 5,
		controls = true,
		muted = true,
		class: className = ''
	}: Props = $props();

	let sourceUrl = $state('');
	let loaded = $state(false);
	let failed = $state(false);
	let isServerSource = $derived(sourceType === 'server' || (typeof source === 'string' && /^(https?:)?\/\//.test(source)));

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

	function handleTimeUpdate(event: Event) {
		if (!preview) return;
		const video = event.currentTarget as HTMLVideoElement;
		if (video.currentTime >= previewSeconds) {
			video.pause();
			video.currentTime = 0;
		}
	}

	function handlePlay(event: Event) {
		if (!preview) return;
		const video = event.currentTarget as HTMLVideoElement;
		if (video.currentTime >= previewSeconds) video.currentTime = 0;
	}
</script>

<div class={`relative overflow-hidden rounded-xl ${className}`}>
	{#if isServerSource && !loaded && !failed}
		<LoadingShimmer class="absolute inset-0 z-10 h-full w-full rounded-none" label="영상 불러오는 중" />
	{/if}

	{#if failed}
		<div class="flex min-h-48 items-center justify-center bg-muted px-4 text-center text-sm text-muted-foreground" role="alert">
			영상을 불러올 수 없습니다.
		</div>
	{:else}
		<video
			src={sourceUrl}
			controls={controls}
			muted={muted}
			playsinline
			preload={isServerSource ? 'metadata' : 'auto'}
			onloadeddata={() => (loaded = true)}
			onerror={() => (failed = true)}
			onplay={handlePlay}
			ontimeupdate={handleTimeUpdate}
			class={`block min-h-48 w-full bg-black object-contain transition-opacity ${isServerSource && !loaded ? 'opacity-0' : 'opacity-100'}`}
		>
			영상을 재생할 수 없습니다.
		</video>
	{/if}

	{#if preview}
		<p class="absolute bottom-2 left-2 rounded-md bg-black/65 px-2 py-1 text-[11px] font-medium text-white">
			앞 {previewSeconds}초 미리보기
		</p>
	{/if}
</div>
