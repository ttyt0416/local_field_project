<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Bookmark, Check, Pencil, Plus, Trash2 } from '@lucide/svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import ImagePresetModal from '../../../components/presets/image-preset-modal.svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import Tab from '../../../components/tabs/tab.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import VideoPresetModal from '../../../components/presets/video-preset-modal.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';
	import { imageGenerationModeTabs, imageModelFamilyTabs, imagePresetCategories, type ImageGenerationMode, type ImageModelFamily, type ImageOptions, type ImagePresetType, type Preset, type PresetType } from '$lib/types/presets';

	type PresetMediaTab = 'image' | 'video';
	const presetMediaTabs: { value: PresetMediaTab; label: string }[] = [
		{ value: 'image', label: 'IMAGE' },
		{ value: 'video', label: 'VIDEO' }
	];

	let ready = $state(false);
	let optionsLoading = $state(true);
	let presetsLoading = $state(true);
	let error = $state('');
	let success = $state('');
	let presets = $state<Preset[]>([]);
	let activeType = $state<PresetType>('t2i_anima');
	let activePresetMedia = $derived<PresetMediaTab>(activeType === 'video' ? 'video' : 'image');
	let activeImagePreset = $derived(
		activeType === 'video'
			? imagePresetCategories[0]
			: imagePresetCategories.find((category) => category.value === activeType) ?? imagePresetCategories[0]
	);
	let isUnavailableKreaPreset = $derived(activeType !== 'video' && activeImagePreset.value === 'i2i_krea2');
	let options = $state<ImageOptions>({ checkpoints: [], loras: [], samplers: [], schedulers: [], default_checkpoint: '', default_sampler: '', default_scheduler: '' });
	let editingPreset = $state<Preset | null>(null);
	let imageEditorOpen = $state(false);
	let videoEditorOpen = $state(false);
	let deleteTarget = $state<Preset | null>(null);
	let deleteModalOpen = $state(false);
	let deleting = $state(false);
	let defaultUpdatingId = $state<string | null>(null);
	let presetRequestId = 0;

	onMount(() => {
		void initialize();
	});

	async function loadPresets() {
		const requestId = ++presetRequestId;
		presetsLoading = true;
		try {
			const loaded = await apiJson<Preset[]>(`presets?type=${activeType}`);
			if (requestId === presetRequestId) presets = loaded;
		} catch (reason) {
			if (requestId === presetRequestId) {
				error = getErrorMessage(reason);
				presets = [];
			}
		} finally {
			if (requestId === presetRequestId) presetsLoading = false;
		}
	}

	async function loadImageOptions(type: ImagePresetType) {
		const family = imagePresetCategories.find((category) => category.value === type)?.modelFamily ?? 'anima';
		optionsLoading = true;
		if (type === 'i2i_krea2') {
			options = { checkpoints: [], loras: [], samplers: [], schedulers: [], default_checkpoint: '', default_sampler: '', default_scheduler: '' };
			optionsLoading = false;
			return;
		}
		try {
			options = await apiJson<ImageOptions>(`generation/image/options?family=${family}`);
		} catch (reason) {
			error = getErrorMessage(reason);
		} finally {
			optionsLoading = false;
		}
	}

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			await loadImageOptions('t2i_anima');
			await loadPresets();
		} catch (reason) {
			error = getErrorMessage(reason);
			presetsLoading = false;
		} finally {
			optionsLoading = false;
			ready = true;
		}
	}

	function selectPresetType(type: PresetType) {
		if (activeType === type) return;
		activeType = type;
		editingPreset = null;
		imageEditorOpen = false;
		videoEditorOpen = false;
		deleteModalOpen = false;
		deleteTarget = null;
		error = '';
		if (type !== 'video') void loadImageOptions(type);
		void loadPresets();
	}

	function selectPresetMedia(media: PresetMediaTab) {
		selectPresetType(media === 'image' ? 't2i_anima' : 'video');
	}

	function selectImageFamily(family: ImageModelFamily) {
		const type = imagePresetCategories.find(
			(category) => category.modelFamily === family && category.generationMode === activeImagePreset.generationMode
		)?.value;
		if (type) selectPresetType(type);
	}

	function selectImageMode(mode: ImageGenerationMode) {
		const type = imagePresetCategories.find(
			(category) => category.modelFamily === activeImagePreset.modelFamily && category.generationMode === mode
		)?.value;
		if (type) selectPresetType(type);
	}

	function openNew() {
		if (isUnavailableKreaPreset) return;
		editingPreset = null;
		if (activeType !== 'video') imageEditorOpen = true;
		else videoEditorOpen = true;
	}

	function openEdit(preset: Preset) {
		if (preset.type === 'i2i_krea2') return;
		editingPreset = preset;
		if (preset.type !== 'video') imageEditorOpen = true;
		else videoEditorOpen = true;
	}

	function handleSaved(saved: Preset) {
		const editing = presets.some((preset) => preset.id === saved.id);
		presets = editing ? presets.map((preset) => (preset.id === saved.id ? saved : preset)) : [saved, ...presets];
		editingPreset = null;
		success = editing ? `'${saved.name}' 프리셋을 수정했습니다.` : `'${saved.name}' 프리셋을 저장했습니다.`;
	}

	function requestDelete(preset: Preset) {
		deleteTarget = preset;
		deleteModalOpen = true;
		error = '';
	}

	function cancelDelete() {
		if (deleting) return;
		deleteModalOpen = false;
		deleteTarget = null;
	}

	async function deletePreset() {
		if (!deleteTarget || deleting) return;
		deleting = true;
		try {
			await apiDelete(`presets/${deleteTarget.id}?type=${deleteTarget.type}`);
			presets = presets.filter((preset) => preset.id !== deleteTarget?.id);
			deleteModalOpen = false;
			deleteTarget = null;
			success = '프리셋을 삭제했습니다.';
		} catch (reason) {
			error = getErrorMessage(reason);
		} finally {
			deleting = false;
		}
	}

	async function setDefaultPreset(preset: Preset) {
		if (defaultUpdatingId) return;
		defaultUpdatingId = preset.id;
		error = '';
		try {
			const updated = await apiJson<Preset>(`presets/${preset.id}`, {
				method: 'PUT',
				json: { type: preset.type, name: preset.name, values: preset.values, is_default: !preset.is_default }
			});
			presets = presets.map((item) =>
				item.id === updated.id ? updated : { ...item, is_default: false }
			);
			success = updated.is_default ? `'${updated.name}'을 기본 프리셋으로 설정했습니다.` : '기본 프리셋을 해제했습니다.';
		} catch (reason) {
			error = getErrorMessage(reason);
		} finally {
			defaultUpdatingId = null;
		}
	}

	function savedPresetLabels(preset: Preset) {
		const labels: Record<string, string> =
			preset.type !== 'video'
				? {
						prompt: '긍정 프롬프트',
						negative_prompt: '부정 프롬프트',
						checkpoint: '체크포인트',
						loras: 'LoRA',
						aspect_ratio: '이미지 비율·크기',
						denoise: 'Denoise',
						cfg: 'CFG',
						steps: 'Steps',
						prompt_enhancement_enabled: '프롬프트 개선 설정',
						improved_prompt: '프롬프트 개선 설정'
					}
				: { prompt: '프롬프트', mode: '생성 방식', size: '영상 크기', duration: '길이(초)', fps: 'FPS', seed: 'Seed', random_seed: 'Seed' };
		const fields = new Set(preset.saved_fields);
		if (preset.type !== 'video' && fields.has('aspect_ratio')) {
			fields.delete('width');
			fields.delete('height');
		}
		if (preset.type !== 'video' && (fields.has('prompt_enhancement_enabled') || fields.has('improved_prompt'))) {
			fields.delete('prompt_enhancement_enabled');
			fields.delete('improved_prompt');
			fields.add('prompt_enhancement_enabled');
		}
		if (preset.type === 'video' && (fields.has('width') || fields.has('height'))) {
			fields.delete('width');
			fields.delete('height');
			fields.add('size');
		}
		if (preset.type === 'video' && fields.has('random_seed')) {
			fields.delete('random_seed');
			fields.add('seed');
		}
		return [...fields].map((field) => labels[field] ?? field).join(', ');
	}

	function presetTypeLabel(type: PresetType) {
		return type === 'video' ? 'VIDEO' : imagePresetCategories.find((category) => category.value === type)?.label ?? 'IMAGE';
	}

	function getErrorMessage(reason: unknown) {
		return reason instanceof Error ? reason.message : '요청을 처리하지 못했습니다.';
	}
</script>

<svelte:head>
	<title>프리셋 관리 · Local Field</title>
	<meta name="description" content="IMAGE와 VIDEO 프리셋 저장, 수정, 삭제" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="프리셋을 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<Typography as="h1" variant="display">프리셋 관리</Typography>

			<section class="space-y-2" aria-label="프리셋 종류">
				<Tab items={presetMediaTabs} value={activePresetMedia} ariaLabel="프리셋 콘텐츠 종류" onselect={selectPresetMedia} />
				{#if activePresetMedia === 'image'}
					<Tab items={imageModelFamilyTabs} value={activeImagePreset.modelFamily} ariaLabel="IMAGE 모델 family" onselect={selectImageFamily} />
					<Tab items={imageGenerationModeTabs} value={activeImagePreset.generationMode} ariaLabel="IMAGE 생성 방식" onselect={selectImageMode} />
				{/if}
			</section>

			<div class="flex justify-end">
				<PrimaryButton onclick={openNew} disabled={activeType !== 'video' && (optionsLoading || isUnavailableKreaPreset)} deactive={isUnavailableKreaPreset}>
					<Plus size={17} strokeWidth={1.9} />
					<span>새 프리셋</span>
				</PrimaryButton>
			</div>

			{#if presetsLoading}
				<div class="flex justify-center py-12"><LoadingSpinner size="md" label="프리셋 불러오는 중" /></div>
			{:else if presets.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-10 text-center">
					<Bookmark size={28} class="mx-auto text-muted-foreground" strokeWidth={1.6} />
					<Typography as="h2" variant="h2" class="mt-4">저장된 {presetTypeLabel(activeType)} 프리셋이 없습니다.</Typography>
					<p class="mt-2 text-sm text-muted-foreground">새 {presetTypeLabel(activeType)} 프리셋을 만들어 생성 설정을 저장해 주세요.</p>
				</section>
			{:else}
				<section class="grid gap-4 md:grid-cols-2">
					{#each presets as preset (preset.id)}
						<article class="flex min-w-0 items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
							<div class="min-w-0">
								<div class="flex items-center gap-2">
									<Bookmark size={17} class="shrink-0 text-primary" strokeWidth={1.8} />
									<h2 class="truncate text-base font-semibold">{preset.name}</h2>
									{#if preset.is_default}<span class="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">기본 프리셋</span>{/if}
								</div>
								<p class="mt-2 truncate text-xs text-muted-foreground">{presetTypeLabel(preset.type)} · {savedPresetLabels(preset)}</p>
								<p class="mt-1 text-xs text-muted-foreground">수정 {new Date(preset.updated_at).toLocaleString('ko-KR')}</p>
							</div>
							<div class="flex shrink-0 flex-wrap items-center justify-end gap-2">
								<OutlinedButton class="px-3 text-xs" loading={defaultUpdatingId === preset.id} onclick={() => void setDefaultPreset(preset)}>
									{#if preset.is_default}<Check size={14} strokeWidth={2} />{/if}<span>{preset.is_default ? '기본 해제' : '기본 프리셋으로 설정'}</span>
								</OutlinedButton>
								<OutlinedButton class="px-3 text-xs" onclick={() => openEdit(preset)}><Pencil size={14} strokeWidth={1.8} /><span>수정</span></OutlinedButton>
								<IconOutlinedButton ariaLabel="프리셋 삭제" variant="destructive" onclick={() => requestDelete(preset)}><Trash2 size={16} strokeWidth={2} /></IconOutlinedButton>
							</div>
						</article>
					{/each}
				</section>
			{/if}
		</div>
	</Layout>

	{#if activeType !== 'video' && !isUnavailableKreaPreset}
		<ImagePresetModal bind:open={imageEditorOpen} preset={editingPreset} presetType={activeType} options={options} onSaved={handleSaved} />
	{/if}
	<VideoPresetModal bind:open={videoEditorOpen} preset={editingPreset} onSaved={handleSaved} />

	<Modal bind:open={deleteModalOpen} title="프리셋을 삭제하시겠습니까?" description="삭제한 프리셋은 복구할 수 없습니다." closeOnBackdrop={!deleting} onclose={cancelDelete}>
		<p class="text-sm leading-6 text-muted-foreground">'{deleteTarget?.name}' 프리셋을 삭제합니다.</p>
		{#snippet footer()}<OutlinedButton disabled={deleting} onclick={cancelDelete}>취소</OutlinedButton><PrimaryButton loading={deleting} variant="destructive" onclick={() => void deletePreset()}><Trash2 size={16} strokeWidth={2} /><span>삭제</span></PrimaryButton>{/snippet}
	</Modal>

	{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="프리셋 처리 실패" message={error} onclose={() => (error = '')} /></div>{/if}
	{#if success}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="프리셋" message={success} onclose={() => (success = '')} /></div>{/if}
{/if}
