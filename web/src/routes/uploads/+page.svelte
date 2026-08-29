<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { AudioLines, ChevronLeft, ChevronRight, Image as ImageIcon, Trash2, Video } from '@lucide/svelte';
	import ImageMedia from '../../../components/media/image.svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import SearchBar from '../../../components/inputs/searchbar.svelte';
	import Tab from '../../../components/tabs/tab.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import VideoMedia from '../../../components/media/video.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { videoGenerationStore, type VideoLibraryAsset } from '$lib/stores/video-generation.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';
	import { formatFileSize } from '$lib/utils/generation';

	type MediaAsset = VideoLibraryAsset & { source_type: string; created_at: string; content_type: string; size: number };
	type MediaAssetPage = {
		items: MediaAsset[];
		page: number;
		page_size: number;
		total_count: number;
		total_pages: number;
	};
	type Filter = 'all' | 'image' | 'audio' | 'video';
	type Sort = 'latest' | 'oldest' | 'name';

	const uploadTabs: { value: Filter; label: string }[] = [
		{ value: 'all', label: '전체' },
		{ value: 'image', label: '이미지' },
		{ value: 'audio', label: '오디오' },
		{ value: 'video', label: '동영상' }
	];

	const sortOptions = [
		{ value: 'latest', label: '최신순' },
		{ value: 'oldest', label: '오래된순' },
		{ value: 'name', label: '이름순' }
	] as const;

	let ready = $state(false);
	let loading = $state(true);
	let assets = $state<MediaAsset[]>([]);
	let filter = $state<Filter>('all');
	let sort = $state<Sort>('latest');
	let searchQuery = $state('');
	let currentPage = $state(1);
	let totalPages = $state(0);
	let totalCount = $state(0);
	let r2vImageCount = $state(0);
	let r2vVideoCount = $state(0);
	let r2vAudioCount = $state(0);
	let error = $state('');
	let success = $state('');
	let deleteTarget = $state<MediaAsset | null>(null);
	let deleteModalOpen = $state(false);
	let deletingId = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | undefined;
	let filteredAssets = $derived(assets);

	onMount(() => {
		void loadAssets();
	});

	async function loadAssets(requestedPage = currentPage) {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		loading = true;
		try {
			const params = new URLSearchParams({ page: String(requestedPage), sort });
			const query = searchQuery.trim();
			if (query) params.set('search', query);
			if (filter !== 'all') params.set('media_kind', filter);
			const result = await apiJson<MediaAssetPage>(`uploads?${params.toString()}`);
			assets = result.items;
			currentPage = result.page;
			totalPages = result.total_pages;
			totalCount = result.total_count;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '업로드 콘텐츠를 불러오지 못했습니다.';
		} finally {
			loading = false;
			ready = true;
		}
	}

	function changeFilter(nextFilter: Filter) {
		if (filter === nextFilter) return;
		filter = nextFilter;
		void loadAssets(1);
	}

	function handleSearchInput() {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => void loadAssets(1), 300);
	}

	function changeSort() {
		void loadAssets(1);
	}

	function changePage(nextPage: number) {
		if (nextPage < 1 || nextPage > totalPages) return;
		void loadAssets(nextPage);
	}

	function requestDelete(asset: MediaAsset) {
		deleteTarget = asset;
		deleteModalOpen = true;
		error = '';
	}

	function closeDeleteModal() {
		if (deletingId) return;
		deleteModalOpen = false;
		deleteTarget = null;
	}

	async function deleteAsset() {
		const target = deleteTarget;
		if (!target || deletingId) return;
		deletingId = target.file_id;
		try {
			await apiDelete(`uploads/${encodeURIComponent(target.file_id)}`);
			deleteModalOpen = false;
			deleteTarget = null;
			success = `'${target.filename}' 콘텐츠를 삭제했습니다.`;
			const nextPage = assets.length === 1 && currentPage > 1 ? currentPage - 1 : currentPage;
			await loadAssets(nextPage);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '업로드 콘텐츠를 삭제하지 못했습니다.';
		} finally {
			deletingId = '';
		}
	}

	function useAsset(asset: MediaAsset, target: 'i2v' | 'fl2v-first' | 'fl2v-last' | 'r2v-image' | 'r2v-video' | 'r2v-audio') {
		const expectedKind = target === 'r2v-audio' ? 'audio' : target === 'r2v-video' ? 'video' : 'image';
		if (asset.media_kind !== expectedKind) return;
		if (target === 'i2v') videoGenerationStore.setFirstFrame(asset);
		if (target === 'fl2v-first') videoGenerationStore.setFirstFrame(asset, 'fl2v');
		if (target === 'fl2v-last') videoGenerationStore.setLastFrame(asset);
		if (target === 'r2v-image') {
			if (videoGenerationStore.addReferenceImage(asset)) r2vImageCount += 1;
			return;
		}
		if (target === 'r2v-video') {
			if (videoGenerationStore.addReferenceVideo(asset)) r2vVideoCount += 1;
			return;
		}
		if (target === 'r2v-audio') {
			if (videoGenerationStore.addReferenceAudio(asset)) r2vAudioCount += 1;
			return;
		}
		void goto('/generate/video');
	}

	function sourceType(url: string | null): 'external' | 'server' {
		return url && /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function sourceLabel(asset: MediaAsset) {
		return '업로드 콘텐츠';
	}
</script>

<svelte:head>
	<title>업로드 콘텐츠 · Local Field</title>
	<meta name="description" content="동영상 생성에 사용할 사용자의 업로드 콘텐츠" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="업로드 콘텐츠를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div class="flex flex-wrap items-end justify-between gap-4"><div><Typography as="h1" variant="display">업로드 콘텐츠</Typography></div></div>
			<Tab items={uploadTabs} bind:value={filter} ariaLabel="업로드 콘텐츠 종류" onselect={changeFilter} />
			<div class="flex flex-col gap-3 sm:flex-row">
				<SearchBar bind:value={searchQuery} placeholder="파일 이름으로 검색" label="업로드 콘텐츠 이름 검색" class="min-w-0 flex-1" oninput={handleSearchInput} />
				<div class="sm:w-48">
					<label for="uploads-sort" class="sr-only">업로드 콘텐츠 정렬</label>
					<select
						id="uploads-sort"
						bind:value={sort}
						onchange={changeSort}
						class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
					>
						{#each sortOptions as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</div>
			</div>
			{#if r2vImageCount + r2vVideoCount + r2vAudioCount > 0}
				<div class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
					<p class="text-sm text-foreground">R2V 선택: 이미지 {r2vImageCount}개 · 동영상 {r2vVideoCount}개 · 오디오 {r2vAudioCount}개</p>
					<a href="/generate/video" class="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90">R2V 설정 열기</a>
				</div>
			{/if}

			{#if loading}<section class="flex min-h-[24rem] items-center justify-center"><LoadingSpinner size="lg" label="콘텐츠를 불러오는 중" /></section>
			{:else if filteredAssets.length === 0}<section class="rounded-2xl border border-dashed border-border bg-card/70 p-10 text-center"><Typography as="h2" variant="h2">업로드한 콘텐츠가 없습니다.</Typography><Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">동영상 생성에서 기기 콘텐츠를 선택하면 생성 요청 시 이곳에 저장됩니다. 생성 결과는 보관함에서 확인할 수 있습니다.</Typography></section>
			{:else}<div class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{#each filteredAssets as asset (asset.file_id)}<article class="overflow-hidden rounded-2xl border border-border bg-card shadow-sm"><div class="aspect-video bg-muted">{#if asset.url && asset.media_kind === 'image'}<ImageMedia source={asset.url} sourceType={sourceType(asset.url)} alt={asset.filename} class="h-full" />{:else if asset.url && asset.media_kind === 'video'}<VideoMedia source={asset.url} sourceType="server" preview={false} muted={false} class="h-full" />{:else if asset.url && asset.media_kind === 'audio'}<div class="flex h-full flex-col items-center justify-center gap-4 p-6"><AudioLines size={36} class="text-primary" /><audio src={asset.url} controls class="w-full"></audio></div>{:else}<div class="flex h-full items-center justify-center text-sm text-muted-foreground">미리보기를 사용할 수 없습니다.</div>{/if}</div><div class="space-y-3 p-4"><div class="flex items-center gap-2 text-xs text-muted-foreground">{#if asset.media_kind === 'image'}<ImageIcon size={14} />{:else if asset.media_kind === 'audio'}<AudioLines size={14} />{:else}<Video size={14} />{/if}<span>{sourceLabel(asset)}</span><span>·</span><span>{new Date(asset.created_at).toLocaleDateString('ko-KR')}</span><span>·</span><span>{formatFileSize(asset.size)}</span></div><div class="flex items-center justify-between gap-2"><a href={`/uploads/${encodeURIComponent(asset.file_id)}`} class="min-w-0 truncate text-sm font-medium text-foreground hover:text-primary hover:underline" title={asset.filename}>{asset.filename}</a><IconOutlinedButton variant="destructive" ariaLabel={`${asset.filename} 삭제`} onclick={() => requestDelete(asset)}><Trash2 size={16} strokeWidth={1.9} /></IconOutlinedButton></div>{#if asset.media_kind === 'image'}<div class="grid grid-cols-2 gap-2"><OutlinedButton class="px-2 text-xs" onclick={() => useAsset(asset, 'i2v')}>I2V 시작</OutlinedButton><OutlinedButton class="px-2 text-xs" onclick={() => useAsset(asset, 'r2v-image')}>R2V 추가</OutlinedButton></div><div class="grid grid-cols-2 gap-2"><OutlinedButton class="px-2 text-xs" onclick={() => useAsset(asset, 'fl2v-first')}>FL2V 첫 프레임</OutlinedButton><OutlinedButton class="px-2 text-xs" onclick={() => useAsset(asset, 'fl2v-last')}>FL2V 마지막</OutlinedButton></div>{:else if asset.media_kind === 'video'}<OutlinedButton class="w-full px-2 text-xs" onclick={() => useAsset(asset, 'r2v-video')}>R2V 동영상 추가</OutlinedButton>{:else}<OutlinedButton class="w-full px-2 text-xs" onclick={() => useAsset(asset, 'r2v-audio')}>R2V 오디오 추가</OutlinedButton>{/if}</div></article>{/each}</div>{/if}
			{#if totalPages > 1}
				<nav class="flex items-center justify-center gap-4 pt-2" aria-label="업로드 콘텐츠 페이지 이동">
					<button type="button" aria-label="이전 업로드 콘텐츠 페이지" disabled={currentPage <= 1} onclick={() => changePage(currentPage - 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft size={18} /></button>
					<span class="text-sm font-medium text-muted-foreground">{currentPage} / {totalPages}</span>
					<button type="button" aria-label="다음 업로드 콘텐츠 페이지" disabled={currentPage >= totalPages} onclick={() => changePage(currentPage + 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronRight size={18} /></button>
				</nav>
			{/if}
		</div>
	</Layout>

	<Modal
		bind:open={deleteModalOpen}
		title="업로드 콘텐츠를 삭제하시겠습니까?"
		description="삭제한 콘텐츠와 파일은 복구할 수 없습니다."
		closeOnBackdrop={!deletingId}
		onclose={closeDeleteModal}
	>
		<p class="text-sm leading-6 text-muted-foreground">'{deleteTarget?.filename}' 콘텐츠와 파일 스토리지 원본을 함께 삭제합니다.</p>
		{#snippet footer()}
			<OutlinedButton disabled={Boolean(deletingId)} onclick={closeDeleteModal}>취소</OutlinedButton>
			<PrimaryButton loading={Boolean(deletingId)} variant="destructive" onclick={() => void deleteAsset()}>
				<Trash2 size={16} strokeWidth={2} />
				<span>삭제</span>
			</PrimaryButton>
		{/snippet}
	</Modal>

	{#if error}
		<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="업로드 콘텐츠 처리 실패" message={error} onclose={() => (error = '')} /></div>
	{/if}
	{#if success}
		<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="업로드 콘텐츠" message={success} onclose={() => (success = '')} /></div>
	{/if}
{/if}
