<script lang="ts">
	import { browser } from '$app/environment';
	import { ChevronLeft, ChevronRight, X } from '@lucide/svelte';
	import LoadingShimmer from '../loadings/loading-shimmer.svelte';
	import { apiBlob } from '$lib/utils/api';

	type MediaSource = string | Blob;
	type GalleryItem = {
		source: string;
		alt?: string;
		sourceType?: 'local' | 'server' | 'external';
	};
	type Props = {
		source: MediaSource;
		alt: string;
		sourceType?: 'local' | 'server' | 'external';
		gallery?: readonly GalleryItem[];
		class?: string;
	};

	let {
		source,
		alt,
		sourceType = 'local',
		gallery = [],
		class: className = ''
	}: Props = $props();

	let sourceUrl = $state('');
	let loaded = $state(false);
	let failed = $state(false);
	let open = $state(false);
	let activeIndex = $state(0);
	let activeLoaded = $state(false);
	let closeButton = $state<HTMLButtonElement>();
	let isExternalSource = $derived(sourceType === 'external');
	let isServerSource = $derived(sourceType === 'server' || (!isExternalSource && typeof source === 'string' && /^(https?:)?\/\//.test(source)));
	let isRemoteSource = $derived(isServerSource || isExternalSource);
	let galleryItems = $derived(gallery.length > 0 ? gallery : sourceUrl ? [{ source: sourceUrl, alt, sourceType }] : []);
	let activeItem = $derived(galleryItems[activeIndex] ?? galleryItems[0]);
	let activeIsExternal = $derived(activeItem?.sourceType === 'external');
	let activeIsServer = $derived(activeItem?.sourceType === 'server' || (!activeIsExternal && Boolean(activeItem?.source && /^(https?:)?\/\//.test(activeItem.source))));
	let activeIsRemote = $derived(activeIsServer || activeIsExternal);

	$effect(() => {
		loaded = false;
		failed = false;
		if (typeof source === 'string' && !isServerSource) {
			sourceUrl = source;
			return;
		}
		if (typeof source === 'string' && isServerSource) {
			let cancelled = false;
			let objectUrl = '';
			sourceUrl = '';
			void apiBlob(source)
				.then((blob) => {
					if (cancelled) return;
					objectUrl = URL.createObjectURL(blob);
					sourceUrl = objectUrl;
				})
				.catch(() => {
					if (!cancelled) failed = true;
				});
			return () => {
				cancelled = true;
				if (objectUrl) URL.revokeObjectURL(objectUrl);
			};
		}
		if (!browser || typeof source === 'string') {
			sourceUrl = '';
			return;
		}
		const objectUrl = URL.createObjectURL(source);
		sourceUrl = objectUrl;
		return () => URL.revokeObjectURL(objectUrl);
	});

	$effect(() => {
		if (open) {
			activeLoaded = false;
			closeButton?.focus();
		}
	});

	function openGallery() {
		if (!sourceUrl || failed) return;
		activeIndex = 0;
		activeLoaded = false;
		open = true;
	}

	function closeGallery() {
		open = false;
	}

	function moveGallery(direction: 1 | -1) {
		if (galleryItems.length < 2) return;
		activeIndex = (activeIndex + direction + galleryItems.length) % galleryItems.length;
		activeLoaded = false;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (!open) return;
		if (event.key === 'Escape') closeGallery();
		if (event.key === 'ArrowRight') moveGallery(1);
		if (event.key === 'ArrowLeft') moveGallery(-1);
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) closeGallery();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class={`relative overflow-hidden rounded-xl ${className}`}>
	{#if isRemoteSource && !loaded && !failed}
		<LoadingShimmer class="absolute inset-0 z-10 h-full w-full rounded-none" label="이미지 불러오는 중" />
	{/if}

	{#if failed}
		<div class="flex min-h-48 items-center justify-center bg-muted px-4 text-center text-sm text-muted-foreground" role="alert">
			이미지를 불러올 수 없습니다.
		</div>
	{:else}
		<button
			type="button"
			class="block h-full w-full cursor-zoom-in focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
			disabled={!sourceUrl}
			aria-label={`${alt} 확대 보기`}
			onclick={openGallery}
		>
			<img
				src={sourceUrl}
				{alt}
				loading={isRemoteSource ? 'lazy' : 'eager'}
				onload={() => (loaded = true)}
				onerror={() => (failed = true)}
				class={`block h-full min-h-48 w-full object-cover transition-opacity ${isRemoteSource && !loaded ? 'opacity-0' : 'opacity-100'}`}
			/>
		</button>
	{/if}
</div>

{#if open && activeItem}
	<dialog
		open
		class="fixed inset-0 z-50 m-0 flex h-full w-full max-w-none items-center justify-center border-0 bg-black/85 p-4"
		aria-modal="true"
		aria-label="이미지 갤러리"
		onclick={handleBackdropClick}
	>
		<div class="relative flex max-h-full max-w-6xl items-center justify-center">
			<button
				bind:this={closeButton}
				type="button"
				class="absolute right-2 top-2 z-20 inline-flex size-10 items-center justify-center rounded-full bg-black/60 text-white transition hover:bg-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				aria-label="이미지 갤러리 닫기"
				onclick={closeGallery}
			>
				<X size={20} strokeWidth={2} />
			</button>

			{#if galleryItems.length > 1}
				<button
					type="button"
					class="absolute left-2 top-1/2 z-20 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-full bg-black/60 text-white transition hover:bg-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					aria-label="이전 이미지"
					onclick={() => moveGallery(-1)}
				>
					<ChevronLeft size={22} strokeWidth={2} />
				</button>
				<button
					type="button"
					class="absolute right-2 top-1/2 z-20 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-full bg-black/60 text-white transition hover:bg-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					aria-label="다음 이미지"
					onclick={() => moveGallery(1)}
				>
					<ChevronRight size={22} strokeWidth={2} />
				</button>
			{/if}

			{#if activeIsRemote && !activeLoaded}
				<LoadingShimmer class="h-[70vh] w-[min(90vw,72rem)] rounded-xl" label="이미지 불러오는 중" />
			{/if}
			<img
				 src={activeItem.source}
				alt={activeItem.alt ?? alt}
				onload={() => (activeLoaded = true)}
				class={`max-h-[90vh] max-w-[90vw] rounded-xl object-contain ${activeIsRemote && !activeLoaded ? 'absolute opacity-0' : 'opacity-100'}`}
			/>
		</div>
	</dialog>
{/if}
