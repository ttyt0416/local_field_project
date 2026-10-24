<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Copy, ChevronLeft, ChevronRight, Plus } from '@lucide/svelte';
	import LoadingSpinner from '../loadings/loading-spinner.svelte';
	import IconOutlinedButton from '../buttons/icon-outlined-button.svelte';
	import Tab from '../tabs/tab.svelte';
	import SearchBar from '../inputs/searchbar.svelte';
	import Toast from '../feedback/toast.svelte';
	import Typography from '../typography/typography.svelte';
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
	type Sort = 'match' | 'similarity' | 'usage';
	type Category = '' | '0' | '1' | '3' | '4' | '5' | '6';

	const categories: { value: Category; label: string }[] = [
		{ value: '', label: '전체' },
		{ value: '0', label: '일반' },
		{ value: '1', label: '아티스트' },
		{ value: '3', label: '저작물' },
		{ value: '4', label: '캐릭터' },
		{ value: '5', label: '메타' },
		{ value: '6', label: '기타' }
	] as const;
	const categoryLabels: Record<number, string> = { 0: '일반', 3: '저작물', 4: '캐릭터' };
	const sortOptions: { value: Sort; label: string }[] = [
		{ value: 'match', label: '일치순' },
		{ value: 'similarity', label: '정확도순' },
		{ value: 'usage', label: '사용순' }
	];

	let loading = $state(true);
	let tags = $state<DanbooruTag[]>([]);
	let searchQuery = $state('');
	let category = $state<Category>('');
	let { onadd, source = 'danbooru' }: { onadd: (text: string) => void; source?: 'danbooru' | 'gelbooru' } = $props();
	let label = $derived(source === 'danbooru' ? 'Danbooru' : 'Gelbooru');
	let active = true;
	let requestId = 0;
	let sort = $state<Sort>('match');
	let currentPage = $state(1);
	let totalPages = $state(0);
	let totalCount = $state(0);
	let error = $state('');
	let success = $state('');
	let copying = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | undefined;

	onMount(() => {
		void loadTags();
		return () => {
			active = false;
			requestId += 1;
			if (searchTimer) clearTimeout(searchTimer);
		};
	});

	async function loadTags(requestedPage = currentPage) {
		const request = ++requestId;
		await authStore.initialize();
		if (!active || request !== requestId) return;
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		loading = true;
		error = '';
		try {
			const params = new URLSearchParams({ page: String(requestedPage), sort });
			if (searchQuery.trim()) params.set('search', searchQuery.trim());
			if (category) params.set('category', category);
			const result = await apiJson<DanbooruTagPage>(`${source === 'gelbooru' ? 'tags/gelbooru' : 'tags'}?${params.toString()}`);
			if (!active || request !== requestId) return;
			tags = result.items;
			currentPage = result.page;
			totalPages = result.total_pages;
			totalCount = result.total_count;
		} catch (reason) {
			if (!active || request !== requestId) return;
			error = reason instanceof Error ? reason.message : `${label} 태그를 불러오지 못했습니다.`;
		} finally {
			if (active && request === requestId) { loading = false; }
		}
	}

	function handleSearchInput() {
		requestId += 1;
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => void loadTags(1), 300);
	}

	function selectCategory(value: Category) {
		if (category === value) return;
		category = value;
		void loadTags(1);
	}

	function changeSort() {
		void loadTags(1);
	}

	function changePage(nextPage: number) {
		if (nextPage < 1 || nextPage > totalPages) return;
		void loadTags(nextPage);
	}

	async function copyTag(tag: string) {
		if (copying) return;
		copying = tag;
		try {
			await navigator.clipboard.writeText(tag);
			success = `'${tag}' 태그를 복사했습니다.`;
		} catch {
			error = '태그를 복사하지 못했습니다.';
		} finally { copying = ''; }
	}

	function addTag(tag: string) { onadd(tag); }

	function categoryLabel(value: number) {
		return categoryLabels[value] ?? ({1:'아티스트',5:'메타',6:'기타'}[value] ?? `분류 ${value}`);
	}
</script>

<p class="text-sm text-muted-foreground">{totalCount.toLocaleString('ko-KR')}개</p>
<div class="space-y-3">
				<div class="flex flex-col gap-3 sm:flex-row"><SearchBar id="danbooru-tag-search" bind:value={searchQuery} placeholder="tag 또는 별칭 검색" label={`${label} 태그 검색`} class="min-w-0 flex-1" oninput={handleSearchInput} /><div class="sm:w-40"><label for="danbooru-tag-sort" class="sr-only">태그 정렬</label><select id="danbooru-tag-sort" bind:value={sort} onchange={changeSort} class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20">{#each sortOptions.filter((option) => source === 'danbooru' || option.value !== 'similarity') as option}<option value={option.value}>{option.label}</option>{/each}</select></div></div>
				{#if sort === 'similarity' && !searchQuery.trim()}<p class="text-xs text-muted-foreground">정확도순은 검색어를 입력하면 pgvector로 정렬합니다.</p>{/if}
				<Tab items={categories.filter((item) => source === 'gelbooru' || ['', '0', '3', '4'].includes(item.value))} bind:value={category} ariaLabel={`${label} 태그 분류`} onselect={selectCategory} class="overflow-x-auto [&>button]:min-w-20" />
			</div>

			{#if loading}
				<section class="flex min-h-[24rem] items-center justify-center"><LoadingSpinner size="lg" label="태그를 불러오는 중" /></section>
			{:else if tags.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-10 text-center"><Typography as="h2" variant="h2">일치하는 태그가 없습니다.</Typography><Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">다른 tag나 별칭으로 검색해 주세요.</Typography></section>
			{:else}
				<section class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
					{#each tags as item (item.tag)}
						<article class="space-y-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
							<div class="flex items-start justify-between gap-3"><div class="min-w-0"><code class="block truncate text-sm font-semibold text-foreground" title={item.tag}>{item.tag}</code><span class="mt-2 inline-flex rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">{categoryLabel(item.category)}</span></div><div class="flex shrink-0 gap-2"><IconOutlinedButton ariaLabel={`${item.tag} 선택한 태그에 추가`} title="선택한 태그에 추가" onclick={() => addTag(item.tag)}><Plus size={16} strokeWidth={1.9} /></IconOutlinedButton><IconOutlinedButton ariaLabel={`${item.tag} 복사`} title="태그 바로 복사" loading={copying === item.tag} disabled={copying !== ''} onclick={() => void copyTag(item.tag)}><Copy size={16} strokeWidth={1.9} /></IconOutlinedButton></div></div>
							<p class="text-xs text-muted-foreground">사용 {item.post_count.toLocaleString('ko-KR')}회</p>
							{#if item.aliases.length > 0}<p class="line-clamp-2 text-xs leading-5 text-muted-foreground" title={item.aliases.join(', ')}>별칭: {item.aliases.slice(0, 6).join(', ')}</p>{/if}
						</article>
					{/each}
				</section>
			{/if}

			{#if totalPages > 1}
				<nav class="flex items-center justify-center gap-4 pt-2" aria-label="태그 페이지 이동"><button type="button" aria-label="이전 태그 페이지" disabled={loading || currentPage <= 1} onclick={() => changePage(currentPage - 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft size={18} /></button><span class="text-sm font-medium text-muted-foreground">{currentPage} / {totalPages}</span><button type="button" aria-label="다음 태그 페이지" disabled={loading || currentPage >= totalPages} onclick={() => changePage(currentPage + 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronRight size={18} /></button></nav>
			{/if}
{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title={`${label} 태그`} message={error} onclose={() => (error = '')} /></div>{/if}
{#if success}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title={`${label} 태그`} message={success} onclose={() => (success = '')} /></div>{/if}
