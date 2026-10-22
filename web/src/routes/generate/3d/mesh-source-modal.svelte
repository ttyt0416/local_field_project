<script module lang="ts">
	export type StoredMeshSource = {
		file_id: string;
		filename: string;
		url: string | null;
		source_type: string;
		created_at: string;
	};
	export type MeshSourceSelection = { kind: 'device'; file: File } | { kind: 'stored'; asset: StoredMeshSource };
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { ChevronLeft, ChevronRight } from '@lucide/svelte';
	import Modal from '../../../../components/modals/modal.svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import SearchBar from '../../../../components/inputs/searchbar.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import { apiJson } from '$lib/utils/api';
	import { imageModelFamilyTabs, imageGenerationModeTabs, imagePresetCategories, type ImagePresetType, type ImageModelFamily, type ImageGenerationMode } from '$lib/types/presets';

	type SourceLocation = 'device' | 'stored';
	type StoredSource = 'uploaded' | 'generated';
	type StoredPage = { items: StoredMeshSource[]; page: number; total_pages: number };
	type Props = {
		open: boolean;
		onselect: (source: MeshSourceSelection) => void;
		onerror: (message: string) => void;
	};
	let { open = $bindable(false), onselect, onerror }: Props = $props();
	const locationTabs = [{ value: 'device' as const, label: '기기 저장소' }, { value: 'stored' as const, label: '보관함' }];
	const sourceTabs = [{ value: 'uploaded' as const, label: '업로드' }, { value: 'generated' as const, label: '생성' }];
	const inputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const fileClass = 'block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary';
	let location = $state<SourceLocation>('stored');
	let source = $state<StoredSource>('generated');
	let presetType = $state<ImagePresetType>('t2i_anima');
	let preset = $derived(imagePresetCategories.find((item) => item.value === presetType) ?? imagePresetCategories[0]);
	let assets = $state<StoredMeshSource[]>([]);
	let loading = $state(false);
	let search = $state('');
	let sort = $state<'latest' | 'oldest' | 'name'>('latest');
	let page = $state(1);
	let totalPages = $state(0);
	let requestId = 0;
	let active = true;

	onMount(() => {
		void loadAssets(1);
		return () => { active = false; requestId += 1; };
	});

	async function loadAssets(requestedPage: number) {
		const currentRequest = ++requestId;
		loading = true;
		try {
			const params = new URLSearchParams({ include_generated: 'true', media_kind: 'image', source, search, sort, page: String(requestedPage) });
			if (source === 'generated') {
				params.set('model_family', preset.modelFamily);
				params.set('generation_mode', preset.generationMode);
			}
			const result = await apiJson<StoredPage>(`uploads?${params.toString()}`);
			if (active && currentRequest === requestId) {
				assets = result.items;
				page = result.page;
				totalPages = result.total_pages;
			}
		} catch (reason) {
			if (active && currentRequest === requestId) onerror(reason instanceof Error ? reason.message : '보관함 이미지를 불러오지 못했습니다.');
		} finally {
			if (active && currentRequest === requestId) loading = false;
		}
	}

	function selectLocation(value: SourceLocation) {
		location = value;
		requestId += 1;
		loading = false;
		if (value === 'stored') void loadAssets(1);
	}

	function selectStoredSource(value: StoredSource) {
		if (source === value) return;
		source = value;
		void loadAssets(1);
	}

	function selectPreset(value: ImagePresetType | undefined) {
		if (!value || presetType === value) return;
		presetType = value;
		void loadAssets(1);
	}

	function selectFamily(family: ImageModelFamily) {
		selectPreset(imagePresetCategories.find((item) => item.modelFamily === family && item.generationMode === preset.generationMode)?.value
			?? imagePresetCategories.find((item) => item.modelFamily === family)?.value);
	}

	function selectMode(mode: ImageGenerationMode) {
		selectPreset(imagePresetCategories.find((item) => item.modelFamily === preset.modelFamily && item.generationMode === mode)?.value
			?? imagePresetCategories.find((item) => item.modelFamily === 'anima' && item.generationMode === mode)?.value);
	}

	function selectDevice(event: Event) {
		if (!(event.currentTarget instanceof HTMLInputElement)) return;
		const file = event.currentTarget.files?.[0];
		if (!file) return;
		onselect({ kind: 'device', file });
		open = false;
	}

	function selectAsset(asset: StoredMeshSource) {
		onselect({ kind: 'stored', asset });
		open = false;
	}

	function searchAssets(event: Event) {
		if (event.currentTarget instanceof HTMLInputElement) search = event.currentTarget.value;
		void loadAssets(1);
	}
</script>

<Modal bind:open title="소스 이미지 선택" description="기기 저장소 또는 보관함에서 3D 모델로 변환할 이미지 한 장을 선택해 주세요.">
	<div class="space-y-5">
		<Tab items={locationTabs} bind:value={location} ariaLabel="이미지 선택 위치" onselect={selectLocation} />
		{#if location === 'device'}
			<label class="block space-y-2" for="mesh-device-file"><span class="text-sm font-medium">파일 선택</span><input id="mesh-device-file" type="file" accept="image/*" class={fileClass} onchange={selectDevice} /></label>
		{:else}
			<div class="space-y-4">
				<Tab items={sourceTabs} bind:value={source} ariaLabel="보관함 이미지 종류" onselect={selectStoredSource} />
				{#if source === 'generated'}
					<div class="space-y-2" aria-label="생성 이미지 분류">
						<Tab items={imageModelFamilyTabs} value={preset.modelFamily} ariaLabel="생성 이미지 모델 family" onselect={selectFamily} />
						<Tab items={imageGenerationModeTabs.filter((item) => (preset.modelFamily !== 'moss' || item.value === 't2i') && (preset.modelFamily !== 'qwen_image_2_1' || item.value === 'i2i'))} value={preset.generationMode} ariaLabel="생성 이미지 방식" onselect={selectMode} />
					</div>
				{/if}
				<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
					<SearchBar id="mesh-stored-search" bind:value={search} label="보관함 이미지 검색" placeholder="파일명으로 검색" oninput={searchAssets} />
					<label class="flex items-center gap-2 text-sm" for="mesh-stored-sort"><span class="sr-only">정렬</span><select id="mesh-stored-sort" bind:value={sort} onchange={(event) => { sort = event.currentTarget.value as typeof sort; void loadAssets(1); }} class={inputClass}><option value="latest">최신순</option><option value="oldest">오래된순</option><option value="name">이름순</option></select></label>
				</div>
				{#if loading}
					<div class="flex min-h-48 items-center justify-center"><LoadingSpinner size="md" label="보관함 이미지를 불러오는 중" /></div>
				{:else if assets.length === 0}
					<p class="py-8 text-center text-sm text-muted-foreground">선택할 이미지가 없습니다.</p>
				{:else}
					<div class="grid grid-cols-2 gap-3">
						{#each assets as asset (asset.file_id)}
							<div class="overflow-hidden rounded-xl border border-border bg-card">
								<div class="aspect-video bg-muted">
									{#if asset.url}<ImageMedia source={asset.url} sourceType={/^(https?:)?\/\//.test(asset.url) ? 'external' : 'server'} alt={asset.filename} class="h-full" />{:else}<div class="flex h-full items-center justify-center text-xs text-muted-foreground">미리보기 없음</div>{/if}
								</div>
								<div class="space-y-2 p-2.5"><p class="truncate text-xs" title={asset.filename}>{asset.filename}</p><div class="flex items-center justify-between gap-2 text-[11px] text-muted-foreground"><span>{asset.source_type === 'image_generation' ? '생성 이미지' : '업로드 이미지'}</span><span>{new Date(asset.created_at).toLocaleDateString('ko-KR')}</span></div><OutlinedButton class="w-full px-2 text-xs" onclick={() => selectAsset(asset)}>선택</OutlinedButton></div>
							</div>
						{/each}
					</div>
					{#if totalPages > 1}
						<nav class="flex items-center justify-center gap-4 pt-2" aria-label="보관함 이미지 페이지 이동"><IconOutlinedButton ariaLabel="이전 보관함 이미지 페이지" disabled={page <= 1} onclick={() => void loadAssets(page - 1)}><ChevronLeft size={18} /></IconOutlinedButton><span class="text-sm font-medium text-muted-foreground">{page} / {totalPages}</span><IconOutlinedButton ariaLabel="다음 보관함 이미지 페이지" disabled={page >= totalPages} onclick={() => void loadAssets(page + 1)}><ChevronRight size={18} /></IconOutlinedButton></nav>
					{/if}
				{/if}
			</div>
		{/if}
	</div>
	{#snippet footer()}<OutlinedButton onclick={() => (open = false)}>닫기</OutlinedButton>{/snippet}
</Modal>
