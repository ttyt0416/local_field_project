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

	let ready = $state(false);
	let images = $state<VaultImage[]>([]);
	let searchQuery = $state('');
	let sort = $state<Sort>('latest');
	let favoritesOnly = $state(page.url.searchParams.get('favorites') === 'true');
	let error = $state('');
	let deleteTarget = $state<VaultImage | null>(null);
	let deleteModalOpen = $state(false);
	let deletingId = $state('');
	let favoriteUpdatingId = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | undefined;
	let generatedCount = $derived(images.filter((image) => image.status === 'completed').length);

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

	async function deleteImage() {
		const target = deleteTarget;
		if (!target || deletingId) return;
		deletingId = target.id;
		try {
			await apiDelete(`vault/images/${target.id}`);
			images = images.filter((image) => image.id !== target.id);
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
				<p class="text-sm font-medium text-muted-foreground">생성된 이미지</p>
				<p class="text-2xl font-semibold tracking-tight">{generatedCount}</p>
			</div>

			{#if images.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-8 text-center sm:p-12">
					<Typography as="h2" variant="h2">{searchQuery || favoritesOnly ? '조건에 맞는 이미지가 없습니다.' : '생성된 이미지가 없습니다.'}</Typography>
					<Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">
						{searchQuery || favoritesOnly ? '검색어 또는 즐겨찾기 조건을 바꿔 다시 시도해 주세요.' : '이미지를 생성하면 이 보관함에 결과가 표시됩니다.'}
					</Typography>
				</section>
			{:else}
				<section class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
					{#each images as image (image.id)}
						<article class="relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition hover:border-primary/40 hover:shadow-md">
							<a
								href={`/vault/images/${image.id}`}
								aria-label={`${image.prompt || image.checkpoint} 이미지 상세 보기`}
								class="absolute inset-0 z-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							></a>
							<div class="pointer-events-none relative z-10">
								<div class="relative">
									{#if image.image_url}
										<ImageMedia source={imageSource(image)} sourceType={imageSourceType(imageSource(image))} alt="생성 이미지" class="aspect-square" />
									{:else}
										<div class="flex aspect-square items-center justify-center bg-muted text-sm text-muted-foreground">이미지 준비 중</div>
									{/if}
									<IconOutlinedButton
										ariaLabel={image.is_favorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
										pressed={image.is_favorite}
										loading={favoriteUpdatingId === image.id}
										class={`pointer-events-auto absolute right-3 top-3 z-10 bg-card/90 shadow-lg ${image.is_favorite ? 'border-primary bg-primary/10 text-primary' : ''}`}
										onclick={() => void toggleFavorite(image)}
									>
										<Heart size={17} strokeWidth={1.9} fill={image.is_favorite ? 'currentColor' : 'none'} />
									</IconOutlinedButton>
									<IconOutlinedButton
										ariaLabel="이미지 삭제"
										loading={deletingId === image.id}
										variant="destructive"
										class="pointer-events-auto absolute bottom-3 right-3 z-10 shadow-lg"
										onclick={() => requestDelete(image)}
									>
										<Trash2 size={17} strokeWidth={2} />
									</IconOutlinedButton>
								</div>
								<div class="space-y-3 p-4">
									<div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
										<span>{image.media_type} · {statusLabel(image.status)}</span>
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

	{#if error}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="보관함 작업 실패" message={error} onclose={() => (error = '')} />
		</div>
	{/if}
{/if}
