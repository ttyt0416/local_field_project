<script module lang="ts">
	export type StoredRiggingSource = { id: string; model_url: string; label: string };
	export type RiggingSourceSelection = { kind: 'device'; file: File } | { kind: 'stored'; asset: StoredRiggingSource };
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { Box, ChevronLeft, ChevronRight } from '@lucide/svelte';
	import Modal from '../../../../components/modals/modal.svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import ModelViewer from '../../../../components/media/model-viewer.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import SearchBar from '../../../../components/inputs/searchbar.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import { apiJson } from '$lib/utils/api';
	import { formatFileSize, formatKstDateTime } from '$lib/utils/generation';

	type SourceLocation = 'device' | 'stored';
	type Sort = 'latest' | 'oldest' | 'most_viewed';
	type StoredModel = {
		id: string; generation_mode?: 'mesh' | 'rigging'; status: string;
		model_url: string | null; source_image_url: string | null;
		created_at: string; preset: 'preview' | 'standard' | 'high'; file_size_bytes: number | null;
	};
	type StoredPage = { items: StoredModel[]; page: number; total_pages: number };
	type Props = { open: boolean; onselect: (selection: RiggingSourceSelection) => void; onerror: (message: string) => void };
	let { open = $bindable(false), onselect, onerror }: Props = $props();
	const locationTabs = [{ value: 'device' as const, label: '기기 저장소' }, { value: 'stored' as const, label: '저장된 콘텐츠' }];
	const inputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const fileClass = 'block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary';
	let location = $state<SourceLocation>('stored');
	let assets = $state<StoredModel[]>([]);
	let loading = $state(false);
	let search = $state('');
	let sort = $state<Sort>('latest');
	let page = $state(1);
	let totalPages = $state(0);
	let previewId = $state('');
	let requestId = 0;
	let active = true;

	onMount(() => {
		void loadAssets(1);
		return () => { active = false; requestId += 1; };
	});

	async function loadAssets(requestedPage: number) {
		const currentRequest = ++requestId;
		previewId = '';
		loading = true;
		try {
			const params = new URLSearchParams({ search, sort, page: String(requestedPage) });
			const result = await apiJson<StoredPage>(`vault/3d?${params.toString()}`);
			if (!active || currentRequest !== requestId) return;
			assets = result.items.filter((asset) => asset.status === 'completed' && asset.generation_mode !== 'rigging' && asset.model_url);
			page = result.page;
			totalPages = result.total_pages;
		} catch (reason) {
			if (active && currentRequest === requestId) onerror(reason instanceof Error ? reason.message : '저장된 3D 모델을 불러오지 못했습니다.');
		} finally {
			if (active && currentRequest === requestId) loading = false;
		}
	}

	function selectLocation(value: SourceLocation) {
		location = value;
		previewId = '';
		requestId += 1;
		loading = false;
		if (value === 'stored') void loadAssets(1);
	}

	function selectDevice(event: Event) {
		if (!(event.currentTarget instanceof HTMLInputElement)) return;
		const file = event.currentTarget.files?.[0];
		if (!file) return;
		if (!file.name.toLowerCase().endsWith('.glb') || file.size > 200 * 1024 * 1024) {
			onerror('200MB 이하의 GLB 파일을 선택해 주세요.');
			event.currentTarget.value = '';
			return;
		}
		onselect({ kind: 'device', file });
		open = false;
	}

	function modelLabel(asset: StoredModel) {
		const preset = { preview: '미리보기', standard: '표준', high: '고품질' }[asset.preset] ?? 'MESH';
		return `${preset} · ${formatKstDateTime(asset.created_at)} · ${asset.id.slice(0, 8)}`;
	}

	function selectAsset(asset: StoredModel) {
		if (!asset.model_url) return;
		onselect({ kind: 'stored', asset: { id: asset.id, model_url: asset.model_url, label: modelLabel(asset) } });
		open = false;
	}

	function searchAssets(event: Event) {
		if (event.currentTarget instanceof HTMLInputElement) search = event.currentTarget.value;
		void loadAssets(1);
	}
</script>

<Modal bind:open title="소스 GLB 선택" description="기기 저장소 또는 저장된 콘텐츠에서 리깅할 모델을 선택해 주세요.">
	<div class="space-y-5">
		<Tab items={locationTabs} bind:value={location} ariaLabel="콘텐츠 선택 위치" onselect={selectLocation} />
		{#if location === 'device'}
			<div class="space-y-2">
				<label class="block space-y-2" for="rigging-device-file"><span class="text-sm font-medium">파일 선택</span><input id="rigging-device-file" type="file" accept=".glb,model/gltf-binary" class={fileClass} onchange={selectDevice} /></label>
				<p class="text-xs text-muted-foreground">200MB 이하 · 리깅되지 않은 GLB 메시</p>
			</div>
		{:else}
			<div class="space-y-4">
				<p class="text-sm font-medium">생성된 MESH</p>
				<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
					<SearchBar id="rigging-stored-search" bind:value={search} label="저장 콘텐츠 검색" placeholder="원본 파일명으로 검색" oninput={searchAssets} />
					<label class="flex items-center gap-2 text-sm" for="rigging-stored-sort"><span class="sr-only">정렬</span><select id="rigging-stored-sort" bind:value={sort} onchange={(event) => { sort = event.currentTarget.value as Sort; void loadAssets(1); }} class={inputClass}><option value="latest">최신순</option><option value="oldest">오래된순</option><option value="most_viewed">많이 본 순</option></select></label>
				</div>
				{#if loading}
					<div class="flex min-h-48 items-center justify-center"><LoadingSpinner size="md" label="저장 콘텐츠를 불러오는 중" /></div>
				{:else if assets.length === 0}
					<p class="py-8 text-center text-sm text-muted-foreground">이 페이지에 선택할 MESH 결과가 없습니다.</p>
				{:else}
					<div class="grid grid-cols-2 gap-3">
						{#each assets as asset (asset.id)}
							<div class="overflow-hidden rounded-xl border border-border bg-card">
								<div class={previewId === asset.id ? 'h-64 bg-muted' : 'aspect-video bg-muted'}>
									{#if previewId === asset.id && asset.model_url}
										<ModelViewer source={asset.model_url} sourceType="server" alt={`${modelLabel(asset)} 3D 미리보기`} class="h-full" />
									{:else if asset.source_image_url}
										<ImageMedia source={asset.source_image_url} sourceType={/^(https?:)?\/\//.test(asset.source_image_url) ? 'external' : 'server'} alt={modelLabel(asset)} class="h-full" />
									{:else}
										<div class="flex h-full items-center justify-center text-muted-foreground"><Box size={28} /></div>
									{/if}
								</div>
								<div class="space-y-2 p-2.5">
									<p class="truncate text-xs" title={modelLabel(asset)}>{modelLabel(asset)}</p>
									<div class="flex items-center justify-between gap-2 text-[11px] text-muted-foreground"><span>생성 MESH</span><span>{formatFileSize(asset.file_size_bytes)}</span></div>
									<OutlinedButton class="w-full px-2 text-xs" active={previewId === asset.id} onclick={() => (previewId = previewId === asset.id ? '' : asset.id)}>{previewId === asset.id ? '미리보기 닫기' : '3D 미리보기'}</OutlinedButton>
									<OutlinedButton class="w-full px-2 text-xs" onclick={() => selectAsset(asset)}>선택</OutlinedButton>
								</div>
							</div>
						{/each}
					</div>
				{/if}
				{#if totalPages > 1}
					<nav class="flex items-center justify-center gap-4 pt-2" aria-label="저장 콘텐츠 페이지 이동"><IconOutlinedButton ariaLabel="이전 저장 콘텐츠 페이지" disabled={loading || page <= 1} onclick={() => void loadAssets(page - 1)}><ChevronLeft size={18} /></IconOutlinedButton><span class="text-sm font-medium text-muted-foreground">{page} / {totalPages}</span><IconOutlinedButton ariaLabel="다음 저장 콘텐츠 페이지" disabled={loading || page >= totalPages} onclick={() => void loadAssets(page + 1)}><ChevronRight size={18} /></IconOutlinedButton></nav>
				{/if}
			</div>
		{/if}
	</div>
	{#snippet footer()}<OutlinedButton onclick={() => (open = false)}>닫기</OutlinedButton>{/snippet}
</Modal>
