<script lang="ts">
	import { onMount } from 'svelte';
	import { Copy, Plus, ChevronLeft, ChevronRight, ExternalLink } from '@lucide/svelte';
	import SearchBar from '../inputs/searchbar.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import IconOutlinedButton from '../buttons/icon-outlined-button.svelte';
	import LoadingSpinner from '../loadings/loading-spinner.svelte';
	import Toast from '../feedback/toast.svelte';
	import ImageMedia from '../media/image.svelte';
	import { apiJson } from '$lib/utils/api';

	type Kind = 'characters' | 'artists' | 'series';
	type Entry = { slug: string; name: string; trigger: string; tags: string[]; copyright: string | null; copyright_name: string | null; count: number; thumb_url: string | null; source_url: string };
	type Page = { items: Entry[]; page: number; total_count: number; total_pages: number; catalogue_version: string; imported_at: string; warning: string | null };
	let { kind, series = '', onadd, onseries }: { kind: Kind; series?: string; onadd: (text: string) => void; onseries: (slug: string) => void } = $props();
	let search = $state('');
	let sort = $state<'count' | 'name'>('count');
	let result = $state<Page | null>(null);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let copying = $state('');
	let active = true;
	let requestId = 0;
	let timer: ReturnType<typeof setTimeout> | undefined;
	let label = $derived(kind === 'characters' ? '캐릭터' : kind === 'artists' ? '아티스트' : '시리즈');
	onMount(() => { void load(); return () => { active = false; requestId += 1; if (timer) clearTimeout(timer); }; });

	async function load(page = 1) {
		if (timer) clearTimeout(timer);
		const request = ++requestId;
		loading = true; error = '';
		try {
			const params = new URLSearchParams({search: search.trim(), sort, page: String(page), series});
			const data = await apiJson<Page>(`tags/catalogue/${kind}?${params}`);
			if (active && request === requestId) result = data;
		} catch (reason) { if (active && request === requestId) { result = null; error = reason instanceof Error ? reason.message : `${label} 검색에 실패했습니다.`; } }
		finally { if (active && request === requestId) loading = false; }
	}
	function schedule() { requestId += 1; loading = true; if (timer) clearTimeout(timer); timer = setTimeout(() => void load(), 300); }
	async function copy(entry: Entry) {
		if (copying) return;
		copying = entry.slug;
		try { await navigator.clipboard.writeText(entry.trigger); if (active) notice = '트리거 프롬프트를 복사했습니다.'; }
		catch { if (active) error = '트리거 프롬프트를 복사하지 못했습니다.'; }
		finally { if (active) copying = ''; }
	}
</script>

<section class="space-y-4" aria-label={`로컬 ${label} 탐색`}>
	<div class="flex flex-col gap-3 sm:flex-row"><SearchBar id={`catalogue-${kind}-search`} bind:value={search} label={`${label} 검색`} placeholder={kind === 'characters' ? '캐릭터명, 작품명 또는 태그로 검색' : `${label} 이름으로 검색`} class="min-w-0 flex-1" oninput={schedule} /><label class="sm:w-40"><span class="sr-only">{label} 정렬</span><select bind:value={sort} onchange={() => void load()} class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm"><option value="count">{kind === 'series' ? '캐릭터 수순' : '사용순'}</option><option value="name">이름순</option></select></label></div>
	<div class="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground"><p>AnimaDex 로컬 카탈로그</p>{#if result}<span>{result.total_count.toLocaleString('ko-KR')}개 · 갱신 {new Date(result.imported_at).toLocaleDateString('ko-KR')}</span>{/if}</div>
	{#if result?.warning}<p class="rounded-lg border border-border bg-muted p-3 text-xs text-muted-foreground">{result.warning} 마지막으로 가져온 로컬 데이터로 검색합니다.</p>{/if}
	{#if loading}<div class="flex min-h-64 items-center justify-center"><LoadingSpinner label={`${label} 검색 중`} /></div>
	{:else if error && !result}<div class="space-y-3 rounded-xl border border-destructive/30 bg-card p-5"><h2 class="text-sm font-semibold">로컬 카탈로그를 사용할 수 없습니다.</h2><p class="text-sm text-destructive" role="alert">{error}</p><OutlinedButton loading={loading} onclick={() => void load()}>다시 확인</OutlinedButton></div>
	{:else if !result?.items.length}<p class="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">검색 결과가 없습니다. 다른 이름이나 태그를 입력해 주세요.</p>
	{:else}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
			{#each result.items as item (item.slug)}
				<article class="min-w-0 space-y-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
					{#if item.thumb_url}<ImageMedia source={item.thumb_url} sourceType="server" alt={`${item.name} 썸네일`} class="aspect-[4/3] w-full bg-muted [&_img]:object-contain" onerror={(message) => (error = message)} />{:else}<div class="flex aspect-[4/3] items-center justify-center rounded-xl bg-muted text-xs text-muted-foreground">등록된 썸네일이 없습니다.</div>{/if}
					<div><h2 class="truncate font-semibold" title={item.name}>{item.name}</h2>{#if item.copyright_name}<button type="button" class="mt-1 max-w-full truncate text-left text-xs text-primary hover:underline" onclick={() => item.copyright && onseries(item.copyright)}>{item.copyright_name}</button>{/if}<p class="mt-1 text-xs text-muted-foreground">{kind === 'series' ? `캐릭터 ${item.count.toLocaleString('ko-KR')}명` : `사용 ${item.count.toLocaleString('ko-KR')}회`}</p></div>
					<p class="break-words text-xs leading-5 text-muted-foreground">{item.trigger}</p>
					{#if item.tags.length}<div class="flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">{#each item.tags as tag}<button type="button" class="rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground hover:bg-primary/10 hover:text-primary" title={`${tag} 선택한 태그에 추가`} onclick={() => onadd(tag)}>{tag}</button>{/each}</div>{/if}
					<div class="flex flex-wrap items-center justify-end gap-2">{#if kind === 'series'}<OutlinedButton class="min-h-8 px-2 py-1 text-xs" onclick={() => onseries(item.slug)}>캐릭터 보기</OutlinedButton>{/if}<IconOutlinedButton ariaLabel={`${item.name} 트리거 추가`} title="트리거 추가" onclick={() => onadd(item.trigger)}><Plus size={15} /></IconOutlinedButton><IconOutlinedButton ariaLabel={`${item.name} 트리거 복사`} title="트리거 복사" loading={copying === item.slug} disabled={copying !== ''} onclick={() => void copy(item)}><Copy size={15} /></IconOutlinedButton><a href={item.source_url} target="_blank" rel="noopener noreferrer" aria-label={`${item.name} AnimaDex에서 보기`} class="rounded-lg border border-border p-2 text-muted-foreground hover:bg-muted"><ExternalLink size={15} /></a></div>
				</article>
			{/each}
		</div>
		{#if result.total_pages > 1}<nav class="flex items-center justify-center gap-4 pt-3" aria-label={`${label} 페이지 이동`}><IconOutlinedButton ariaLabel={`이전 ${label} 페이지`} disabled={loading || result.page <= 1} onclick={() => void load((result?.page ?? 1) - 1)}><ChevronLeft size={18} /></IconOutlinedButton><span class="text-sm text-muted-foreground">{result.page} / {result.total_pages}</span><IconOutlinedButton ariaLabel={`다음 ${label} 페이지`} disabled={loading || result.page >= result.total_pages} onclick={() => void load((result?.page ?? 1) + 1)}><ChevronRight size={18} /></IconOutlinedButton></nav>{/if}
	{/if}
</section>
{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title={`${label} 검색`} message={error} onclose={() => (error = '')} /></div>{/if}
{#if notice}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="태그 탐색기" message={notice} onclose={() => (notice = '')} /></div>{/if}
