<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Copy, X } from '@lucide/svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import Tab from '../../../components/tabs/tab.svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import BooruBrowser from '../../../components/tags/booru-browser.svelte';
	import CatalogueBrowser from '../../../components/tags/catalogue-browser.svelte';
	import { authStore } from '$lib/stores/auth.svelte';

	type ExplorerTab = 'danbooru' | 'gelbooru' | 'characters' | 'artists' | 'series';
	const tabs = [{value:'danbooru',label:'Danbooru'},{value:'gelbooru',label:'Gelbooru'},{value:'characters',label:'캐릭터'},{value:'artists',label:'아티스트'},{value:'series',label:'시리즈'}] as const;
	let selected = $state<ExplorerTab>('danbooru');
	let selectedTags = $state('');
	let series = $state('');
	let ready = $state(false);
	let copying = $state(false);
	let error = $state('');
	let notice = $state('');
	onMount(() => { let active = true; void initialize(); async function initialize() { await authStore.initialize(); if (!active) return; if (!authStore.isAuthenticated) { await goto('/login'); return; } ready = true; } return () => { active = false; }; });
	function add(text: string) { selectedTags = selectedTags.trim() ? `${selectedTags.trim()}, ${text}` : text; }
	function select(value: ExplorerTab) { selected = value; series = ''; }
	function showSeries(slug: string) { series = slug; selected = 'characters'; }
	async function copySelected() {
		if (copying || !selectedTags.trim()) return;
		copying = true;
		try { await navigator.clipboard.writeText(selectedTags.trim()); notice = '선택한 태그를 복사했습니다.'; }
		catch { error = '선택한 태그를 복사하지 못했습니다.'; }
		finally { copying = false; }
	}
</script>

<svelte:head><title>태그 탐색기 · Local Field</title><meta name="description" content="Danbooru·Gelbooru 태그와 캐릭터·아티스트·시리즈 로컬 검색" /></svelte:head>
<Layout>
	<div class="space-y-6">
		<Typography as="h1" variant="display">태그 탐색기</Typography>
		{#if ready}
			<Tab items={tabs} value={selected} ariaLabel="탐색 종류" onselect={select} class="overflow-x-auto [&>button]:min-w-20" />
			<section class="space-y-2"><div class="flex items-center justify-between gap-3"><label for="selected-explorer-tags" class="text-sm font-semibold">선택한 태그</label><IconOutlinedButton ariaLabel="선택한 태그 복사" loading={copying} disabled={!selectedTags.trim()} onclick={() => void copySelected()}><Copy size={16} /></IconOutlinedButton></div><textarea id="selected-explorer-tags" bind:value={selectedTags} rows="3" placeholder="태그·트리거의 추가 버튼을 누르면 기존 내용 뒤에 추가됩니다." class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-primary/20"></textarea></section>
			{#if selected === 'danbooru' || selected === 'gelbooru'}{#key selected}<BooruBrowser source={selected} onadd={add} />{/key}{:else}{#if series}<div class="flex items-center gap-2 text-sm"><span class="text-muted-foreground">시리즈: {series.replaceAll('_',' ')}</span><IconOutlinedButton ariaLabel="시리즈 필터 해제" onclick={() => (series = '')}><X size={14} /></IconOutlinedButton></div>{/if}{#key `${selected}:${series}`}<CatalogueBrowser kind={selected} {series} onadd={add} onseries={showSeries} />{/key}{/if}
		{:else}<LoadingSpinner label="태그 탐색기를 불러오는 중" />{/if}
	</div>
</Layout>
{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="태그 탐색기" message={error} onclose={() => (error = '')} /></div>{/if}
{#if notice}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="태그 탐색기" message={notice} onclose={() => (notice = '')} /></div>{/if}
