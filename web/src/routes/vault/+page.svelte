<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ChevronLeft, ChevronRight, Download, Heart, Trash2, Video } from '@lucide/svelte';
	import ImageMedia from '../../../components/media/image.svelte';
	import VideoMedia from '../../../components/media/video.svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import SearchBar from '../../../components/inputs/searchbar.svelte';
	import Tab from '../../../components/tabs/tab.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';
import { formatElapsedSeconds, formatKstDateTime } from '$lib/utils/generation';
import { downloadMedia } from '$lib/utils/download';

	type Sort = 'latest' | 'oldest' | 'most_viewed';
	const vaultMediaTabs = [
		{ value: 'images' as const, label: '이미지' },
		{ value: 'videos' as const, label: '동영상' }
	];

	type VaultImage = {
		id: string;
		media_type: string;
		status: string;
		prompt: string;
		checkpoint: string;
		image_url: string | null;
		view_count: number;
		is_favorite: boolean;
		created_at: string;
		completed_at: string | null;
		elapsed_seconds: number;
	};

	type VaultVideo = {
		id: string;
		media_type: string;
		mode: 'i2v' | 'fl2v' | 'r2v';
		fps: number;
		status: string;
		prompt: string;
		video_url: string | null;
		view_count: number;
		is_favorite: boolean;
		created_at: string;
		completed_at: string | null;
		elapsed_seconds: number;
	};

	type FavoriteResponse = {
		is_favorite: boolean;
	};

	type VaultPage<T> = {
		items: T[];
		page: number;
		page_size: number;
		total_count: number;
		completed_count: number;
		total_pages: number;
	};

	type BulkDeleteResponse = {
		deleted_count: number;
	};

	let ready = $state(false);
	let mediaTab = $state<'images' | 'videos'>(page.url.searchParams.get('tab') === 'videos' ? 'videos' : 'images');
	let images = $state<VaultImage[]>([]);
	let videos = $state<VaultVideo[]>([]);
	let searchQuery = $state('');
	let sort = $state<Sort>('latest');
	let favoritesOnly = $state(page.url.searchParams.get('favorites') === 'true');
	let imagePage = $state(1);
	let videoPage = $state(1);
	let imageTotalPages = $state(0);
	let videoTotalPages = $state(0);
	let imageCompletedCount = $state(0);
	let videoCompletedCount = $state(0);
	let error = $state('');
	let deleteTarget = $state<VaultImage | null>(null);
	let videoDeleteTarget = $state<VaultVideo | null>(null);
	let deleteModalOpen = $state(false);
	let videoDeleteModalOpen = $state(false);
	let deletingId = $state('');
	let videoDeletingId = $state('');
	let bulkDeleteModalOpen = $state(false);
	let bulkDeleting = $state(false);
	let selectedIds = $state<Set<string>>(new Set());
	let favoriteUpdatingId = $state('');
	let videoFavoriteUpdatingId = $state('');
	let downloadingId = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | undefined;
	let contentCount = $derived(imageCompletedCount);
	let videoCount = $derived(videoCompletedCount);
	let selectedCount = $derived(selectedIds.size);
	let allVisibleSelected = $derived(images.length > 0 && images.every((image) => selectedIds.has(image.id)));

	onMount(() => {
		void loadVault();
	});

	$effect(() => {
		const nextFavoritesOnly = page.url.searchParams.get('favorites') === 'true';
		const nextMediaTab = page.url.searchParams.get('tab') === 'videos' ? 'videos' : 'images';
		if (nextFavoritesOnly === favoritesOnly && nextMediaTab === mediaTab) return;
		favoritesOnly = nextFavoritesOnly;
		mediaTab = nextMediaTab;
		if (ready) void loadVault(1);
	});

	async function loadVault(requestedPage = mediaTab === 'images' ? imagePage : videoPage) {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			const params = new URLSearchParams({ sort, page: String(requestedPage) });
			const query = searchQuery.trim();
			if (query) params.set('search', query);
			if (favoritesOnly) params.set('favorites_only', 'true');
			if (mediaTab === 'images') {
				const result = await apiJson<VaultPage<VaultImage>>(`vault/images?${params.toString()}`);
				images = result.items;
				imagePage = result.page;
				imageTotalPages = result.total_pages;
				imageCompletedCount = result.completed_count;
				selectedIds = new Set();
			} else {
				const result = await apiJson<VaultPage<VaultVideo>>(`vault/videos?${params.toString()}`);
				videos = result.items;
				videoPage = result.page;
				videoTotalPages = result.total_pages;
				videoCompletedCount = result.completed_count;
			}
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '보관함을 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	function handleSearchInput() {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => void loadVault(1), 300);
	}

	function selectVaultMediaTab(nextTab: 'images' | 'videos') {
		const query = favoritesOnly ? `?favorites=true&tab=${nextTab}` : `?tab=${nextTab}`;
		void goto(`/vault${query}`);
	}

	function changePage(nextPage: number) {
		const totalPages = mediaTab === 'images' ? imageTotalPages : videoTotalPages;
		if (nextPage < 1 || nextPage > totalPages) return;
		void loadVault(nextPage);
	}

	function requestDelete(image: VaultImage) {
		deleteTarget = image;
		deleteModalOpen = true;
	}

	function cancelDelete() {
		deleteModalOpen = false;
		deleteTarget = null;
	}

	function toggleSelection(imageId: string, selected: boolean) {
		const next = new Set(selectedIds);
		if (selected) next.add(imageId);
		else next.delete(imageId);
		selectedIds = next;
	}

	function toggleSelectAll() {
		selectedIds = allVisibleSelected ? new Set() : new Set(images.map((image) => image.id));
	}

	function handleSelectionChange(event: Event, imageId: string) {
		if (!(event.currentTarget instanceof HTMLInputElement)) return;
		toggleSelection(imageId, event.currentTarget.checked);
	}

	function requestBulkDelete() {
		if (selectedCount > 0) bulkDeleteModalOpen = true;
	}

	function cancelBulkDelete() {
		bulkDeleteModalOpen = false;
	}

	async function bulkDeleteImages() {
		const generationIds = [...selectedIds];
		if (generationIds.length === 0 || bulkDeleting) return;
		bulkDeleting = true;
		try {
			await apiJson<BulkDeleteResponse>('vault/images/bulk', {
				method: 'DELETE',
				json: { generation_ids: generationIds }
			});
			images = images.filter((image) => !selectedIds.has(image.id));
			selectedIds = new Set();
			bulkDeleteModalOpen = false;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '선택한 콘텐츠를 삭제하지 못했습니다.';
		} finally {
			bulkDeleting = false;
		}
	}

	async function deleteImage() {
		const target = deleteTarget;
		if (!target || deletingId) return;
		deletingId = target.id;
		try {
			await apiDelete(`vault/images/${target.id}`);
			images = images.filter((image) => image.id !== target.id);
			selectedIds = new Set([...selectedIds].filter((id) => id !== target.id));
			deleteModalOpen = false;
			deleteTarget = null;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '콘텐츠를 삭제하지 못했습니다.';
		} finally {
			deletingId = '';
		}
	}

	async function toggleFavorite(image: VaultImage) {
		if (favoriteUpdatingId) return;
		favoriteUpdatingId = image.id;
		try {
			const result = await apiJson<FavoriteResponse>(`vault/images/${image.id}/favorite`, {
				method: 'PATCH',
				json: { is_favorite: !image.is_favorite }
			});
			if (favoritesOnly && !result.is_favorite) {
				images = images.filter((item) => item.id !== image.id);
			} else {
				images = images.map((item) => (item.id === image.id ? { ...item, is_favorite: result.is_favorite } : item));
			}
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '즐겨찾기를 변경하지 못했습니다.';
		} finally {
			favoriteUpdatingId = '';
		}
	}

	async function toggleFavoriteVideo(video: VaultVideo) {
		if (videoFavoriteUpdatingId) return;
		videoFavoriteUpdatingId = video.id;
		try {
			const result = await apiJson<FavoriteResponse>(`vault/videos/${video.id}/favorite`, {
				method: 'PATCH',
				json: { is_favorite: !video.is_favorite }
			});
			if (favoritesOnly && !result.is_favorite) videos = videos.filter((item) => item.id !== video.id);
			else videos = videos.map((item) => (item.id === video.id ? { ...item, is_favorite: result.is_favorite } : item));
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '영상 즐겨찾기를 변경하지 못했습니다.';
		} finally {
			videoFavoriteUpdatingId = '';
		}
	}

	async function downloadImage(image: VaultImage) {
		if (!image.image_url || downloadingId) return;
		downloadingId = image.id;
		try {
			await downloadMedia(image.image_url, `local-field-image-${image.id}.png`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '이미지를 다운로드하지 못했습니다.';
		} finally {
			downloadingId = '';
		}
	}

	async function downloadVideo(video: VaultVideo) {
		if (!video.video_url || downloadingId) return;
		downloadingId = video.id;
		try {
			await downloadMedia(video.video_url, `local-field-video-${video.id}.mp4`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '영상을 다운로드하지 못했습니다.';
		} finally {
			downloadingId = '';
		}
	}

	function requestDeleteVideo(video: VaultVideo) {
		videoDeleteTarget = video;
		videoDeleteModalOpen = true;
	}

	async function deleteVideo() {
		const target = videoDeleteTarget;
		if (!target || videoDeletingId) return;
		videoDeletingId = target.id;
		try {
			await apiDelete(`vault/videos/${target.id}`);
			videos = videos.filter((video) => video.id !== target.id);
			videoDeleteModalOpen = false;
			videoDeleteTarget = null;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '영상을 삭제하지 못했습니다.';
		} finally {
			videoDeletingId = '';
		}
	}

	function videoModeLabel(mode: VaultVideo['mode']) {
		return mode.toUpperCase();
	}

	function imageSource(image: VaultImage) {
		return image.image_url ?? '';
	}

	function imageSourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function statusLabel(status: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패' }[status] ?? status;
	}
</script>

<svelte:head>
	<title>{favoritesOnly ? '즐겨찾기' : '보관함'} · Local Field</title>
	<meta name="description" content="생성된 이미지와 동영상을 검색하고 관리하는 보관함" />
</svelte:head>

<Layout>
	<div class="space-y-8">
		<Typography as="h1" variant="display">{favoritesOnly ? '즐겨찾기' : '보관함'}</Typography>
		<Tab items={vaultMediaTabs} bind:value={mediaTab} ariaLabel="보관함 콘텐츠 종류" onselect={selectVaultMediaTab} />

		<div class="flex flex-col gap-3 sm:flex-row">
			<SearchBar bind:value={searchQuery} class="min-w-0 flex-1" oninput={handleSearchInput} />
			<div class="sm:w-48">
				<label for="vault-sort" class="sr-only">정렬</label>
				<select
					id="vault-sort"
					bind:value={sort}
					onchange={() => void loadVault(1)}
					class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
				>
					<option value="latest">최신순</option>
					<option value="oldest">오래된순</option>
					<option value="most_viewed">많이 본 순</option>
				</select>
			</div>
		</div>

		{#if !ready}
			<section class="flex min-h-[24rem] items-center justify-center">
				<LoadingSpinner size="lg" label="보관함을 불러오는 중" />
			</section>
		{:else}
			<div class="flex items-center justify-between border-b border-border pb-4">
				<p class="text-sm font-medium text-muted-foreground">{favoritesOnly ? '즐겨찾기 콘텐츠' : '생성된 콘텐츠'}</p>
				<p class="text-2xl font-semibold tracking-tight">{mediaTab === 'images' ? contentCount : videoCount}</p>
			</div>

			{#if mediaTab === 'images'}
			{#if images.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-8 text-center sm:p-12">
					<Typography as="h2" variant="h2">{favoritesOnly ? '즐겨찾기 한 콘텐츠가 없습니다.' : searchQuery ? '조건에 맞는 콘텐츠가 없습니다.' : '생성된 콘텐츠가 없습니다.'}</Typography>
					<Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">
						{favoritesOnly ? '즐겨찾기한 콘텐츠를 추가하면 이곳에 표시됩니다.' : searchQuery ? '검색어를 바꿔 다시 시도해 주세요.' : '이미지를 생성하면 이 보관함에 결과가 표시됩니다.'}
					</Typography>
				</section>
			{:else}
				<section class="space-y-3">
					<div class="flex flex-wrap items-center justify-between gap-3">
						<label class="inline-flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
							<input
								type="checkbox"
								checked={allVisibleSelected}
								onchange={toggleSelectAll}
								aria-label="현재 콘텐츠 전체 선택"
								class="size-5 rounded border-input accent-primary"
							/>
							<span>전체 선택</span>
						</label>
						{#if selectedCount > 0}
							<PrimaryButton
								variant="destructive"
								class="min-h-9 px-3 py-1 text-xs"
								onclick={requestBulkDelete}
							>
								<Trash2 size={14} strokeWidth={2} />
								<span>선택된 {selectedCount}개 콘텐츠 제거</span>
							</PrimaryButton>
						{/if}
					</div>
					<div class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
					{#each images as image (image.id)}
						<article class="relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition hover:border-primary/40 hover:shadow-md">
							<a
								href={`/vault/images/${image.id}`}
								aria-label={`${image.prompt || image.checkpoint} 콘텐츠 상세 보기`}
								class="absolute inset-0 z-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							></a>
							<div class="pointer-events-none relative z-10">
								<div class="relative">
									<label class="pointer-events-auto absolute left-3 top-3 z-10 inline-flex cursor-pointer">
										<span class="sr-only">콘텐츠 선택</span>
										<input
											type="checkbox"
											checked={selectedIds.has(image.id)}
											onchange={(event) => handleSelectionChange(event, image.id)}
											aria-label={`${image.prompt || image.checkpoint} 선택`}
											class="size-5 rounded border-input accent-primary"
										/>
									</label>
									{#if image.image_url}
										<ImageMedia source={imageSource(image)} sourceType={imageSourceType(imageSource(image))} alt="생성 이미지" class="aspect-square" />
									{:else}
										<div class="flex aspect-square items-center justify-center bg-muted text-sm text-muted-foreground">이미지 준비 중</div>
									{/if}
									<div class="pointer-events-auto absolute bottom-3 right-3 z-10 flex flex-col gap-2">
										<IconOutlinedButton
											variant="filled"
											ariaLabel={image.is_favorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
											pressed={image.is_favorite}
											loading={favoriteUpdatingId === image.id}
											class={`${image.is_favorite ? 'bg-primary text-primary-foreground hover:bg-primary/90' : ''} shadow-lg`}
											onclick={() => void toggleFavorite(image)}
										>
											<Heart size={17} strokeWidth={1.9} fill={image.is_favorite ? 'currentColor' : 'none'} />
										</IconOutlinedButton>
										<IconOutlinedButton
											ariaLabel="이미지 다운로드"
											loading={downloadingId === image.id}
											disabled={!image.image_url}
											class="shadow-lg"
											onclick={() => void downloadImage(image)}
										>
											<Download size={17} strokeWidth={1.9} />
										</IconOutlinedButton>
										<IconOutlinedButton
											ariaLabel="콘텐츠 삭제"
											loading={deletingId === image.id}
											variant="destructive"
											class="shadow-lg"
											onclick={() => requestDelete(image)}
										>
											<Trash2 size={17} strokeWidth={2} />
										</IconOutlinedButton>
									</div>
								</div>
								<div class="space-y-3 p-4">
									<div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
										<span>{image.status === 'completed' ? 'IMAGE' : `IMAGE · ${statusLabel(image.status)}`}</span>
										<span>{formatKstDateTime(image.created_at)}</span>
									</div>
									<p class="line-clamp-2 text-sm leading-5 text-foreground">{image.prompt}</p>
									<div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
										<span class="truncate">{image.checkpoint}</span>
										<span class="shrink-0">소요 {formatElapsedSeconds(image.elapsed_seconds)} · 조회 {image.view_count}</span>
									</div>
								</div>
							</div>
						</article>
					{/each}
					</div>
					{#if imageTotalPages > 1}
					<nav class="flex items-center justify-center gap-4 pt-2" aria-label="이미지 페이지 이동">
						<button type="button" aria-label="이전 이미지 페이지" disabled={imagePage <= 1} onclick={() => changePage(imagePage - 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft size={18} /></button>
						<span class="text-sm font-medium text-muted-foreground">{imagePage} / {imageTotalPages}</span>
						<button type="button" aria-label="다음 이미지 페이지" disabled={imagePage >= imageTotalPages} onclick={() => changePage(imagePage + 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronRight size={18} /></button>
					</nav>
					{/if}
					</section>
			{/if}
			{:else}
				{#if videos.length === 0}
					<section class="rounded-2xl border border-dashed border-border bg-card/70 p-8 text-center sm:p-12">
						<Typography as="h2" variant="h2">{favoritesOnly ? '즐겨찾기 한 영상이 없습니다.' : searchQuery ? '조건에 맞는 영상이 없습니다.' : '생성된 영상이 없습니다.'}</Typography>
						<Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">{favoritesOnly ? '영상에 즐겨찾기를 추가하면 이곳에 표시됩니다.' : '동영상을 생성하면 이곳에 결과가 표시됩니다.'}</Typography>
					</section>
				{:else}
					<section class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
						{#each videos as video (video.id)}
							<article class="overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition hover:border-primary/40 hover:shadow-md">
								<div class="relative aspect-video bg-muted">
									{#if video.video_url}<VideoMedia source={video.video_url} sourceType="server" preview={false} muted={false} class="h-full" />{:else}<div class="flex h-full items-center justify-center text-sm text-muted-foreground">영상 준비 중</div>{/if}
								</div>
								<div class="space-y-3 p-4">
									<a href={`/vault/videos/${video.id}`} aria-label={`${video.prompt || videoModeLabel(video.mode)} 콘텐츠 상세 보기`} class="block space-y-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
										<div class="flex items-center justify-between gap-3 text-xs text-muted-foreground"><span>{videoModeLabel(video.mode)} · {statusLabel(video.status)}</span><span>{formatKstDateTime(video.created_at)}</span></div>
										<p class="line-clamp-2 text-sm leading-5 text-foreground transition hover:text-primary">{video.prompt}</p>
									</a>
									<div class="flex items-center justify-between gap-3"><span class="text-xs text-muted-foreground">FPS {video.fps} · 소요 {formatElapsedSeconds(video.elapsed_seconds)} · 조회 {video.view_count}</span><div class="flex gap-2"><IconOutlinedButton ariaLabel="영상 다운로드" loading={downloadingId === video.id} disabled={!video.video_url} onclick={() => void downloadVideo(video)}><Download size={17} strokeWidth={1.9} /></IconOutlinedButton><IconOutlinedButton variant="filled" ariaLabel={video.is_favorite ? '영상 즐겨찾기 해제' : '영상 즐겨찾기 추가'} pressed={video.is_favorite} loading={videoFavoriteUpdatingId === video.id} class={video.is_favorite ? 'bg-primary text-primary-foreground hover:bg-primary/90' : ''} onclick={() => void toggleFavoriteVideo(video)}><Heart size={17} strokeWidth={1.9} fill={video.is_favorite ? 'currentColor' : 'none'} /></IconOutlinedButton><IconOutlinedButton ariaLabel="영상 콘텐츠 삭제" loading={videoDeletingId === video.id} variant="destructive" onclick={() => requestDeleteVideo(video)}><Trash2 size={17} strokeWidth={2} /></IconOutlinedButton></div></div>
								</div>
							</article>
						{/each}
					</section>
					{#if videoTotalPages > 1}
						<nav class="flex items-center justify-center gap-4 pt-2" aria-label="동영상 페이지 이동">
							<button type="button" aria-label="이전 동영상 페이지" disabled={videoPage <= 1} onclick={() => changePage(videoPage - 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft size={18} /></button>
							<span class="text-sm font-medium text-muted-foreground">{videoPage} / {videoTotalPages}</span>
							<button type="button" aria-label="다음 동영상 페이지" disabled={videoPage >= videoTotalPages} onclick={() => changePage(videoPage + 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronRight size={18} /></button>
						</nav>
					{/if}
				{/if}
			{/if}
		{/if}
	</div>
	</Layout>

	<Modal
		bind:open={deleteModalOpen}
		title="콘텐츠를 삭제하시겠습니까?"
		description="삭제한 콘텐츠는 복구할 수 없습니다."
		closeOnBackdrop={!deletingId}
		onclose={cancelDelete}
	>
		<p class="text-sm leading-6 text-muted-foreground">선택한 이미지를 보관함과 파일 스토리지에서 삭제합니다.</p>
		{#snippet footer()}
			<OutlinedButton disabled={Boolean(deletingId)} onclick={cancelDelete}>취소</OutlinedButton>
			<PrimaryButton
				loading={Boolean(deletingId)}
				variant="destructive"
				onclick={() => void deleteImage()}
			>
				<Trash2 size={16} strokeWidth={2} />
				<span>삭제</span>
			</PrimaryButton>
		{/snippet}
	</Modal>

	<Modal
		bind:open={bulkDeleteModalOpen}
		title="선택된 콘텐츠를 삭제하시겠습니까?"
		description="삭제한 콘텐츠와 파일은 복구할 수 없습니다."
		closeOnBackdrop={!bulkDeleting}
		onclose={cancelBulkDelete}
	>
		<p class="text-sm leading-6 text-muted-foreground">선택한 {selectedCount}개의 콘텐츠와 파일 스토리지 원본을 함께 삭제합니다.</p>
		{#snippet footer()}
			<OutlinedButton disabled={bulkDeleting} onclick={cancelBulkDelete}>취소</OutlinedButton>
			<PrimaryButton
				loading={bulkDeleting}
				variant="destructive"
				onclick={() => void bulkDeleteImages()}
			>
				<Trash2 size={16} strokeWidth={2} />
				<span>선택된 콘텐츠 제거</span>
			</PrimaryButton>
		{/snippet}
	</Modal>

	<Modal
		bind:open={videoDeleteModalOpen}
		title="영상을 삭제하시겠습니까?"
		description="삭제한 영상과 파일은 복구할 수 없습니다."
		closeOnBackdrop={!videoDeletingId}
	>
		<p class="text-sm leading-6 text-muted-foreground">선택한 영상을 보관함과 파일 스토리지에서 삭제합니다.</p>
		{#snippet footer()}
			<OutlinedButton disabled={Boolean(videoDeletingId)} onclick={() => (videoDeleteModalOpen = false)}>취소</OutlinedButton>
			<PrimaryButton loading={Boolean(videoDeletingId)} variant="destructive" onclick={() => void deleteVideo()}><Trash2 size={16} strokeWidth={2} /><span>삭제</span></PrimaryButton>
		{/snippet}
	</Modal>

	{#if error}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="보관함 작업 실패" message={error} onclose={() => (error = '')} />
		</div>
	{/if}
