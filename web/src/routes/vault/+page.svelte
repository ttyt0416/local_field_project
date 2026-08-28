<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Heart, Trash2 } from '@lucide/svelte';
	import ImageMedia from '../../../components/media/image.svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import SearchBar from '../../../components/inputs/searchbar.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';

	type Sort = 'latest' | 'oldest' | 'most_viewed';

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
	};

	type FavoriteResponse = {
		is_favorite: boolean;
	};

	type BulkDeleteResponse = {
		deleted_count: number;
	};

	let ready = $state(false);
	let images = $state<VaultImage[]>([]);
	let searchQuery = $state('');
	let sort = $state<Sort>('latest');
	let favoritesOnly = $state(page.url.searchParams.get('favorites') === 'true');
	let error = $state('');
	let deleteTarget = $state<VaultImage | null>(null);
	let deleteModalOpen = $state(false);
	let deletingId = $state('');
	let bulkDeleteModalOpen = $state(false);
	let bulkDeleting = $state(false);
	let selectedIds = $state<Set<string>>(new Set());
	let favoriteUpdatingId = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | undefined;
	let contentCount = $derived(images.filter((image) => image.status === 'completed').length);
	let selectedCount = $derived(selectedIds.size);
	let allVisibleSelected = $derived(images.length > 0 && images.every((image) => selectedIds.has(image.id)));

	onMount(() => {
		void loadVault();
	});

	$effect(() => {
		const nextFavoritesOnly = page.url.searchParams.get('favorites') === 'true';
		if (nextFavoritesOnly === favoritesOnly) return;
		favoritesOnly = nextFavoritesOnly;
		if (ready) void loadVault();
	});

	async function loadVault() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			const params = new URLSearchParams({ sort });
			const query = searchQuery.trim();
			if (query) params.set('search', query);
			if (favoritesOnly) params.set('favorites_only', 'true');
			images = await apiJson<VaultImage[]>(`vault/images?${params.toString()}`);
			selectedIds = new Set();
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '보관함을 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	function handleSearchInput() {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => void loadVault(), 300);
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
			error = reason instanceof Error ? reason.message : '이미지를 삭제하지 못했습니다.';
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
	<meta name="description" content="생성된 이미지를 검색하고 관리하는 보관함" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="보관함을 불러오는 중" />
	</div>
{:else}
	<Layout>
		<div class="space-y-8">
			<Typography as="h1" variant="display">{favoritesOnly ? '즐겨찾기' : '보관함'}</Typography>

			<div class="flex flex-col gap-3 sm:flex-row">
				<SearchBar bind:value={searchQuery} class="min-w-0 flex-1" oninput={handleSearchInput} />
				<div class="sm:w-48">
					<label for="vault-sort" class="sr-only">정렬</label>
					<select
						id="vault-sort"
						bind:value={sort}
						onchange={() => void loadVault()}
						class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
					>
						<option value="latest">최신순</option>
						<option value="oldest">오래된순</option>
						<option value="most_viewed">많이 본 순</option>
					</select>
				</div>
			</div>

			<div class="flex items-center justify-between border-b border-border pb-4">
				<p class="text-sm font-medium text-muted-foreground">{favoritesOnly ? '즐겨찾기 콘텐츠' : '생성된 콘텐츠'}</p>
				<div class="flex items-center gap-3">
					{#if selectedCount > 0}
						<PrimaryButton
							variant="destructive"
							class="min-h-9 px-3 py-1 text-xs"
							onclick={requestBulkDelete}
						>
							<Trash2 size={14} strokeWidth={2} />
							<span>선택된 콘텐츠 삭제</span>
						</PrimaryButton>
					{/if}
					<p class="text-2xl font-semibold tracking-tight">{contentCount}</p>
				</div>
			</div>

			{#if images.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-8 text-center sm:p-12">
					<Typography as="h2" variant="h2">{favoritesOnly ? '즐겨찾기 한 콘텐츠가 없습니다.' : searchQuery ? '조건에 맞는 콘텐츠가 없습니다.' : '생성된 콘텐츠가 없습니다.'}</Typography>
					<Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">
						{favoritesOnly ? '즐겨찾기한 콘텐츠를 추가하면 이곳에 표시됩니다.' : searchQuery ? '검색어를 바꿔 다시 시도해 주세요.' : '이미지를 생성하면 이 보관함에 결과가 표시됩니다.'}
					</Typography>
				</section>
			{:else}
				<section class="space-y-3">
					<div class="flex items-center justify-between">
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
							<span class="text-xs text-muted-foreground">{selectedCount}개 선택됨</span>
						{/if}
					</div>
					<div class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
					{#each images as image (image.id)}
						<article class="relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition hover:border-primary/40 hover:shadow-md">
							<a
								href={`/vault/images/${image.id}`}
								aria-label={`${image.prompt || image.checkpoint} 이미지 상세 보기`}
								class="absolute inset-0 z-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							></a>
							<div class="pointer-events-none relative z-10">
								<div class="relative">
									<label class="pointer-events-auto absolute left-3 top-3 z-10 inline-flex cursor-pointer rounded-md bg-card/90 p-1.5 shadow-lg">
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
											ariaLabel={image.is_favorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
											pressed={image.is_favorite}
											loading={favoriteUpdatingId === image.id}
											class={`bg-card/90 shadow-lg ${image.is_favorite ? 'border-primary bg-primary/10 text-primary' : ''}`}
											onclick={() => void toggleFavorite(image)}
										>
											<Heart size={17} strokeWidth={1.9} fill={image.is_favorite ? 'currentColor' : 'none'} />
										</IconOutlinedButton>
										<IconOutlinedButton
											ariaLabel="이미지 삭제"
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
										<span>{new Date(image.created_at).toLocaleDateString('ko-KR')}</span>
									</div>
									<p class="line-clamp-2 text-sm leading-5 text-foreground">{image.prompt}</p>
									<div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
										<span class="truncate">{image.checkpoint}</span>
										<span class="shrink-0">조회 {image.view_count}</span>
									</div>
								</div>
							</div>
						</article>
					{/each}
					</div>
				</section>
			{/if}
		</div>
	</Layout>

	<Modal
		bind:open={deleteModalOpen}
		title="이미지를 삭제하시겠습니까?"
		description="삭제한 이미지는 복구할 수 없습니다."
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
				<span>선택된 콘텐츠 삭제</span>
			</PrimaryButton>
		{/snippet}
	</Modal>

	{#if error}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="보관함 작업 실패" message={error} onclose={() => (error = '')} />
		</div>
	{/if}
{/if}
