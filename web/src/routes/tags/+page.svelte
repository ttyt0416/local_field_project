<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Copy, ChevronLeft, ChevronRight } from '@lucide/svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import SearchBar from '../../../components/inputs/searchbar.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiJson } from '$lib/utils/api';

	type DanbooruTag = {
		tag: string;
		category: number;
		post_count: number;
		aliases: string[];
	};
	type DanbooruTagPage = {
		items: DanbooruTag[];
		page: number;
		page_size: number;
		total_count: number;
		total_pages: number;
	};

	const categories = [
		{ value: '', label: '전체' },
		{ value: '0', label: '일반' },
		{ value: '3', label: '저작물' },
		{ value: '4', label: '캐릭터' }
	] as const;
	const categoryLabels: Record<number, string> = { 0: '일반', 3: '저작물', 4: '캐릭터' };

	let ready = $state(false);
	let loading = $state(true);
	let tags = $state<DanbooruTag[]>([]);
	let searchQuery = $state('');
	let category = $state('');
	let currentPage = $state(1);
	let totalPages = $state(0);
	let totalCount = $state(0);
	let error = $state('');
	let success = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | undefined;

	onMount(() => {
		void loadTags();
		return () => {
			if (searchTimer) clearTimeout(searchTimer);
		};
	});

	async function loadTags(requestedPage = currentPage) {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		loading = true;
		error = '';
		try {
			const params = new URLSearchParams({ page: String(requestedPage) });
			if (searchQuery.trim()) params.set('search', searchQuery.trim());
			if (category) params.set('category', category);
			const result = await apiJson<DanbooruTagPage>(`tags?${params.toString()}`);
			tags = result.items;
			currentPage = result.page;
			totalPages = result.total_pages;
			totalCount = result.total_count;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : 'Danbooru 태그를 불러오지 못했습니다.';
		} finally {
			loading = false;
			ready = true;
		}
	}

	function handleSearchInput() {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => void loadTags(1), 300);
	}

	function selectCategory(value: string) {
		if (category === value) return;
		category = value;
		void loadTags(1);
	}

	function changePage(nextPage: number) {
		if (nextPage < 1 || nextPage > totalPages) return;
		void loadTags(nextPage);
	}

	async function copyTag(tag: string) {
		try {
			await navigator.clipboard.writeText(tag);
			success = `'${tag}' 태그를 복사했습니다.`;
		} catch {
			error = '태그를 복사하지 못했습니다.';
		}
	}

	function categoryLabel(value: number) {
		return categoryLabels[value] ?? `분류 ${value}`;
	}
</script>

<svelte:head>
	<title>태그 탐색기 · Local Field</title>
	<meta name="description" content="Danbooru 태그, 별칭, 분류, 사용 수 탐색" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="태그 탐색기를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<section class="flex flex-wrap items-end justify-between gap-4">
				<div><Typography as="h1" variant="display">태그 탐색기</Typography><p class="mt-2 text-sm text-muted-foreground">Danbooru tag와 별칭을 탐색하고 바로 복사할 수 있습니다.</p></div>
				<span class="text-sm text-muted-foreground">{totalCount.toLocaleString('ko-KR')}개</span>
			</section>

			<div class="space-y-3">
				<SearchBar id="danbooru-tag-search" bind:value={searchQuery} placeholder="tag 또는 별칭 검색" label="Danbooru 태그 검색" oninput={handleSearchInput} />
				<div class="flex flex-wrap gap-2" aria-label="Danbooru 태그 분류">
					{#each categories as option (option.value)}
						<OutlinedButton class="px-3 text-xs" active={category === option.value} onclick={() => selectCategory(option.value)}>{option.label}</OutlinedButton>
					{/each}
				</div>
			</div>

			{#if loading}
				<section class="flex min-h-[24rem] items-center justify-center"><LoadingSpinner size="lg" label="태그를 불러오는 중" /></section>
			{:else if tags.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-10 text-center"><Typography as="h2" variant="h2">일치하는 태그가 없습니다.</Typography><Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">다른 tag나 별칭으로 검색해 주세요.</Typography></section>
			{:else}
				<section class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
					{#each tags as item (item.tag)}
						<article class="space-y-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
							<div class="flex items-start justify-between gap-3"><div class="min-w-0"><code class="block truncate text-sm font-semibold text-foreground" title={item.tag}>{item.tag}</code><span class="mt-2 inline-flex rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">{categoryLabel(item.category)}</span></div><IconOutlinedButton ariaLabel={`${item.tag} 복사`} onclick={() => void copyTag(item.tag)}><Copy size={16} strokeWidth={1.9} /></IconOutlinedButton></div>
							<p class="text-xs text-muted-foreground">사용 {item.post_count.toLocaleString('ko-KR')}회</p>
							{#if item.aliases.length > 0}<p class="line-clamp-2 text-xs leading-5 text-muted-foreground" title={item.aliases.join(', ')}>별칭: {item.aliases.slice(0, 6).join(', ')}</p>{/if}
						</article>
					{/each}
				</section>
			{/if}

			{#if totalPages > 1}
				<nav class="flex items-center justify-center gap-4 pt-2" aria-label="태그 페이지 이동"><button type="button" aria-label="이전 태그 페이지" disabled={currentPage <= 1} onclick={() => changePage(currentPage - 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft size={18} /></button><span class="text-sm font-medium text-muted-foreground">{currentPage} / {totalPages}</span><button type="button" aria-label="다음 태그 페이지" disabled={currentPage >= totalPages} onclick={() => changePage(currentPage + 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronRight size={18} /></button></nav>
			{/if}
		</div>
	</Layout>
{/if}

{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="태그 탐색기" message={error} onclose={() => (error = '')} /></div>{/if}
{#if success}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="태그 탐색기" message={success} onclose={() => (success = '')} /></div>{/if}
