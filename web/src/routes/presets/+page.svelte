<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Bookmark, Check, Pencil, Plus, Trash2 } from '@lucide/svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import Select from '../../../components/inputs/select.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';

	type AspectRatio = 'custom' | '2:3' | '3:2' | '1:1' | '16:9' | '9:16';
	type LoraSelection = { name: string; strength: number };
	type PresetField =
		| 'prompt'
		| 'negative_prompt'
		| 'checkpoint'
		| 'loras'
		| 'aspect_ratio'
		| 'cfg'
		| 'steps'
		| 'prompt_enhancement';
	type PresetValues = {
		prompt?: string;
		negative_prompt?: string;
		prompt_enhancement_enabled?: boolean;
		improved_prompt?: string;
		checkpoint?: string;
		loras?: LoraSelection[];
		aspect_ratio?: AspectRatio;
		width?: number;
		height?: number;
		cfg?: number;
		steps?: number;
	};
	type Preset = {
		id: string;
		type: 't2i';
		name: string;
		values: PresetValues;
		is_default: boolean;
		saved_fields: string[];
		created_at: string;
		updated_at: string;
	};
	type ImageOptions = { checkpoints: string[]; loras: string[]; default_checkpoint: string };

	const defaultNegativePrompt = 'worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia';
	const numberInputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const aspectRatioOptions: { value: AspectRatio; label: string }[] = [
		{ value: 'custom', label: '커스텀' },
		{ value: '2:3', label: '2:3' },
		{ value: '3:2', label: '3:2' },
		{ value: '1:1', label: '1:1' },
		{ value: '16:9', label: '16:9' },
		{ value: '9:16', label: '9:16' }
	];
	const aspectRatioPresets: Record<AspectRatio, { width: number; height: number } | null> = {
		custom: null,
		'2:3': { width: 768, height: 1152 },
		'3:2': { width: 1152, height: 768 },
		'1:1': { width: 1024, height: 1024 },
		'16:9': { width: 1152, height: 648 },
		'9:16': { width: 648, height: 1152 }
	};
	const presetFieldOptions: { key: PresetField; label: string }[] = [
		{ key: 'prompt', label: '긍정 프롬프트' },
		{ key: 'negative_prompt', label: '부정 프롬프트' },
		{ key: 'checkpoint', label: '체크포인트' },
		{ key: 'loras', label: 'LoRA' },
		{ key: 'aspect_ratio', label: '이미지 비율·크기' },
		{ key: 'cfg', label: 'CFG' },
		{ key: 'steps', label: 'Steps' },
		{ key: 'prompt_enhancement', label: '프롬프트 개선 설정' }
	];
	const allFields: Record<PresetField, boolean> = {
		prompt: true,
		negative_prompt: true,
		checkpoint: true,
		loras: true,
		aspect_ratio: true,
		cfg: true,
		steps: true,
		prompt_enhancement: true
	};

	let ready = $state(false);
	let optionsLoading = $state(true);
	let presetsLoading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let success = $state('');
	let presets = $state<Preset[]>([]);
	let options = $state<ImageOptions>({ checkpoints: [], loras: [], default_checkpoint: '' });
	let editorOpen = $state(false);
	let editingId = $state<string | null>(null);
	let presetName = $state('');
	let prompt = $state('');
	let negativePrompt = $state(defaultNegativePrompt);
	let promptEnhancementEnabled = $state(false);
	let improvedPrompt = $state('');
	let checkpoint = $state('');
	let loras = $state<LoraSelection[]>([]);
	let aspectRatio = $state<AspectRatio>('custom');
	let width = $state(1024);
	let height = $state(1024);
	let cfg = $state(4);
	let steps = $state(30);
	let selectedFields = $state<Record<PresetField, boolean>>({ ...allFields });
	let deleteTarget = $state<Preset | null>(null);
	let deleteModalOpen = $state(false);
	let deleting = $state(false);
	let defaultUpdatingId = $state<string | null>(null);

	let checkpointOptions = $derived(options.checkpoints.map((value) => ({ value, label: value })));
	let loraOptions = $derived(options.loras.map((value) => ({ value, label: value })));

	$effect(() => {
		if (!editorOpen) return;
		const preset = aspectRatioPresets[aspectRatio];
		if (!preset) return;
		width = preset.width;
		height = preset.height;
	});

	onMount(() => {
		void initialize();
	});

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			[presets, options] = await Promise.all([
				apiJson<Preset[]>('presets?type=t2i'),
				apiJson<ImageOptions>('generation/image/options')
			]);
			checkpoint = options.default_checkpoint;
		} catch (reason) {
			error = getErrorMessage(reason);
		} finally {
			presetsLoading = false;
			optionsLoading = false;
			ready = true;
		}
	}

	function openNew() {
		editingId = null;
		presetName = '';
		prompt = '';
		negativePrompt = defaultNegativePrompt;
		promptEnhancementEnabled = false;
		improvedPrompt = '';
		checkpoint = options.default_checkpoint;
		loras = [];
		aspectRatio = 'custom';
		width = 1024;
		height = 1024;
		cfg = 4;
		steps = 30;
		selectedFields = { ...allFields };
		error = '';
		editorOpen = true;
	}

	function openEdit(preset: Preset) {
		const values = preset.values;
		const fields = new Set(preset.saved_fields);
		editingId = preset.id;
		presetName = preset.name;
		prompt = values.prompt ?? '';
		negativePrompt = values.negative_prompt ?? defaultNegativePrompt;
		promptEnhancementEnabled = values.prompt_enhancement_enabled ?? false;
		improvedPrompt = values.improved_prompt ?? '';
		checkpoint = values.checkpoint ?? options.default_checkpoint;
		loras = values.loras?.map(({ name, strength }) => ({ name, strength })) ?? [];
		aspectRatio = values.aspect_ratio ?? 'custom';
		width = values.width ?? 1024;
		height = values.height ?? 1024;
		cfg = values.cfg ?? 4;
		steps = values.steps ?? 30;
		selectedFields = {
			prompt: fields.has('prompt'),
			negative_prompt: fields.has('negative_prompt'),
			checkpoint: fields.has('checkpoint'),
			loras: fields.has('loras'),
			aspect_ratio: fields.has('aspect_ratio'),
			cfg: fields.has('cfg'),
			steps: fields.has('steps'),
			prompt_enhancement: fields.has('prompt_enhancement_enabled') || fields.has('improved_prompt')
		};
		error = '';
		editorOpen = true;
	}

	function availableLoraOptions(index: number) {
		const selected = new Set(loras.filter((_, currentIndex) => currentIndex !== index).map((lora) => lora.name));
		return loraOptions.filter((option) => option.value === loras[index]?.name || !selected.has(option.value));
	}

	function addLora() {
		if (loras.some((lora) => !lora.name) || loras.length >= loraOptions.length) return;
		loras = [...loras, { name: '', strength: 1.0 }];
	}

	function removeLora(index: number) {
		loras = loras.filter((_, currentIndex) => currentIndex !== index);
	}

	function setField(key: PresetField, checked: boolean) {
		selectedFields[key] = checked;
	}

	function selectedFieldCount() {
		return presetFieldOptions.filter(({ key }) => selectedFields[key]).length;
	}

	function buildValues(): PresetValues {
		const values: PresetValues = {};
		if (selectedFields.prompt) values.prompt = prompt.trim();
		if (selectedFields.negative_prompt) values.negative_prompt = negativePrompt.trim();
		if (selectedFields.checkpoint) values.checkpoint = checkpoint;
		if (selectedFields.loras) values.loras = loras.filter(({ name }) => name.trim()).map(({ name, strength }) => ({ name, strength }));
		if (selectedFields.aspect_ratio) {
			values.aspect_ratio = aspectRatio;
			values.width = width;
			values.height = height;
		}
		if (selectedFields.cfg) values.cfg = cfg;
		if (selectedFields.steps) values.steps = steps;
		if (selectedFields.prompt_enhancement) {
			values.prompt_enhancement_enabled = promptEnhancementEnabled;
			if (improvedPrompt.trim()) values.improved_prompt = improvedPrompt.trim();
		}
		return values;
	}

	async function savePreset() {
		error = '';
		if (!presetName.trim()) {
			error = '프리셋 이름을 입력해 주세요.';
			return;
		}
		if (selectedFieldCount() === 0) {
			error = '저장할 설정을 하나 이상 선택해 주세요.';
			return;
		}
		if (selectedFields.prompt && !prompt.trim()) {
			error = '긍정 프롬프트를 입력해 주세요.';
			return;
		}
		if (selectedFields.checkpoint && !checkpoint) {
			error = '체크포인트를 선택해 주세요.';
			return;
		}
		saving = true;
		try {
			const saved = await apiJson<Preset>(editingId ? `presets/${editingId}` : 'presets', {
				method: editingId ? 'PUT' : 'POST',
				json: editingId
					? { name: presetName.trim(), values: buildValues() }
					: { type: 't2i', name: presetName.trim(), values: buildValues() }
			});
			presets = editingId ? presets.map((preset) => (preset.id === saved.id ? saved : preset)) : [saved, ...presets];
			editorOpen = false;
			success = editingId ? `'${saved.name}' 프리셋을 수정했습니다.` : `'${saved.name}' 프리셋을 저장했습니다.`;
		} catch (reason) {
			error = getErrorMessage(reason);
		} finally {
			saving = false;
		}
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
			await apiDelete(`presets/${deleteTarget.id}`);
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
				json: { name: preset.name, values: preset.values, is_default: !preset.is_default }
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
		const fields = new Set(preset.saved_fields);
		if (fields.has('aspect_ratio')) {
			fields.delete('width');
			fields.delete('height');
		}
		if (fields.has('prompt_enhancement_enabled') || fields.has('improved_prompt')) {
			fields.delete('prompt_enhancement_enabled');
			fields.delete('improved_prompt');
			fields.add('prompt_enhancement');
		}
		const labels: Record<string, string> = Object.fromEntries(presetFieldOptions.map(({ key, label }) => [key, label]));
		return [...fields].map((field) => labels[field] ?? field).join(', ');
	}

	function getErrorMessage(reason: unknown) {
		return reason instanceof Error ? reason.message : '요청을 처리하지 못했습니다.';
	}
</script>

<svelte:head>
	<title>프리셋 관리 · Local Field</title>
	<meta name="description" content="이미지 생성 프리셋 저장, 수정, 삭제" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="프리셋을 불러오는 중" />
	</div>
{:else}
	<Layout>
		<div class="space-y-6">
			<section class="flex flex-col gap-5 rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8 md:flex-row md:items-end md:justify-between">
				<div>
					<div class="mb-4 flex size-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
						<Bookmark size={24} strokeWidth={1.8} />
					</div>
					<Typography as="p" variant="eyebrow">Generation presets</Typography>
					<Typography as="h1" variant="display" class="mt-3">프리셋 관리</Typography>
					<Typography as="p" variant="muted" class="mt-3 max-w-2xl text-base">이미지 생성 설정을 저장하고 수정하거나 삭제할 수 있습니다.</Typography>
				</div>
				<PrimaryButton onclick={openNew} disabled={optionsLoading}>
					<Plus size={17} strokeWidth={1.9} />
					<span>새 프리셋</span>
				</PrimaryButton>
			</section>

			{#if presetsLoading}
				<div class="flex justify-center py-12"><LoadingSpinner size="md" label="프리셋 불러오는 중" /></div>
			{:else if presets.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-10 text-center">
					<Bookmark size={28} class="mx-auto text-muted-foreground" strokeWidth={1.6} />
					<Typography as="h2" variant="h2" class="mt-4">저장된 프리셋이 없습니다.</Typography>
					<p class="mt-2 text-sm text-muted-foreground">새 프리셋을 만들어 이미지 생성 설정을 저장해 주세요.</p>
				</section>
			{:else}
				<section class="grid gap-4 md:grid-cols-2">
					{#each presets as preset (preset.id)}
						<article class="flex min-w-0 items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
							<div class="min-w-0">
								<div class="flex items-center gap-2">
									<Bookmark size={17} class="shrink-0 text-primary" strokeWidth={1.8} />
									<h2 class="truncate text-base font-semibold">{preset.name}</h2>
									{#if preset.is_default}
										<span class="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">기본 프리셋</span>
									{/if}
								</div>
								<p class="mt-2 truncate text-xs text-muted-foreground">t2i · {savedPresetLabels(preset)}</p>
								<p class="mt-1 text-xs text-muted-foreground">수정 {new Date(preset.updated_at).toLocaleString('ko-KR')}</p>
							</div>
							<div class="flex shrink-0 flex-wrap items-center justify-end gap-2">
								<OutlinedButton
									class="px-3 text-xs"
									loading={defaultUpdatingId === preset.id}
									onclick={() => void setDefaultPreset(preset)}
								>
									{#if preset.is_default}<Check size={14} strokeWidth={2} />{/if}
									<span>{preset.is_default ? '기본 해제' : '기본 프리셋으로 설정'}</span>
								</OutlinedButton>
								<OutlinedButton class="px-3 text-xs" onclick={() => openEdit(preset)}>
									<Pencil size={14} strokeWidth={1.8} />
									<span>수정</span>
								</OutlinedButton>
								<IconOutlinedButton ariaLabel="프리셋 삭제" variant="destructive" onclick={() => requestDelete(preset)}>
									<Trash2 size={16} strokeWidth={2} />
								</IconOutlinedButton>
							</div>
						</article>
					{/each}
				</section>
			{/if}
		</div>
	</Layout>

	<Modal bind:open={editorOpen} title={editingId ? '프리셋 수정' : '프리셋 저장'} description="이름과 저장할 설정 항목을 선택해 주세요." closeOnBackdrop={!saving}>
		<div class="space-y-5">
			<label class="block space-y-2" for="managed-preset-name">
				<span class="text-sm font-medium">프리셋 이름</span>
				<input id="managed-preset-name" bind:value={presetName} maxlength="100" class={numberInputClass} />
			</label>

			<div class="space-y-3">
				<div class="flex items-center justify-between gap-3">
					<span class="text-sm font-medium">저장할 설정</span>
					<span class="text-xs text-muted-foreground">{selectedFieldCount()}개 선택</span>
				</div>
				<div class="grid gap-2 sm:grid-cols-2">
					{#each presetFieldOptions as field}
						<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted">
							<input type="checkbox" checked={selectedFields[field.key]} onchange={(event) => setField(field.key, (event.currentTarget as HTMLInputElement).checked)} class="size-4 accent-primary" />
							<span>{field.label}</span>
						</label>
					{/each}
				</div>
			</div>

			{#if selectedFields.prompt}
				<label class="block space-y-2" for="managed-prompt">
					<span class="text-sm font-medium">긍정 프롬프트</span>
					<textarea id="managed-prompt" bind:value={prompt} rows="4" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
				</label>
			{/if}
			{#if selectedFields.negative_prompt}
				<label class="block space-y-2" for="managed-negative-prompt">
					<span class="text-sm font-medium">부정 프롬프트</span>
					<textarea id="managed-negative-prompt" bind:value={negativePrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
				</label>
			{/if}
			{#if selectedFields.checkpoint}
				<Select id="managed-checkpoint" label="체크포인트" options={checkpointOptions} bind:value={checkpoint} autocomplete disabled={optionsLoading || checkpointOptions.length === 0} required />
			{/if}
			{#if selectedFields.loras}
				<div class="space-y-3">
					<div class="flex items-center justify-between gap-3">
						<span class="text-sm font-medium">LoRA</span>
						<button type="button" onclick={addLora} disabled={optionsLoading || loraOptions.length === 0 || loras.length >= loraOptions.length || loras.some((lora) => !lora.name)} class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/10 disabled:pointer-events-none disabled:opacity-50"><Plus size={14} strokeWidth={2} /><span>LoRA 추가</span></button>
					</div>
					{#each loras as lora, index (index)}
						<div class="rounded-lg border border-border p-3">
							<div class="flex items-start gap-2">
								<div class="min-w-0 flex-1"><Select id={`managed-lora-${index}`} label={`LoRA ${index + 1}`} options={availableLoraOptions(index)} bind:value={lora.name} autocomplete disabled={optionsLoading} /></div>
								<button type="button" aria-label={`LoRA ${index + 1} 제거`} onclick={() => removeLora(index)} class="mt-7 inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Trash2 size={15} strokeWidth={1.8} /></button>
							</div>
							{#if lora.name}<label class="mt-3 block space-y-2" for={`managed-lora-strength-${index}`}><span class="text-sm font-medium">Strength</span><input id={`managed-lora-strength-${index}`} type="number" min="-2" max="2" step="0.05" bind:value={lora.strength} class={numberInputClass} /></label>{/if}
						</div>
					{/each}
				</div>
			{/if}
			{#if selectedFields.aspect_ratio}
				<Select id="managed-aspect-ratio" label="이미지 비율" options={aspectRatioOptions} bind:value={aspectRatio} />
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="block space-y-2" for="managed-width"><span class="text-sm font-medium">가로</span><input id="managed-width" type="number" min="64" max="2048" step="8" bind:value={width} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} /></label>
					<label class="block space-y-2" for="managed-height"><span class="text-sm font-medium">세로</span><input id="managed-height" type="number" min="64" max="2048" step="8" bind:value={height} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} /></label>
				</div>
			{/if}
			{#if selectedFields.cfg || selectedFields.steps}
				<div class="grid gap-4 sm:grid-cols-2">
					{#if selectedFields.cfg}<label class="block space-y-2" for="managed-cfg"><span class="text-sm font-medium">CFG</span><input id="managed-cfg" type="number" min="0" max="20" step="0.1" bind:value={cfg} class={numberInputClass} /></label>{/if}
					{#if selectedFields.steps}<label class="block space-y-2" for="managed-steps"><span class="text-sm font-medium">Steps</span><input id="managed-steps" type="number" min="1" max="100" step="1" bind:value={steps} class={numberInputClass} /></label>{/if}
				</div>
			{/if}
			{#if selectedFields.prompt_enhancement}
				<label class="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm"><input type="checkbox" bind:checked={promptEnhancementEnabled} class="size-4 accent-primary" /><span>프롬프트 개선 사용</span></label>
				<label class="block space-y-2" for="managed-improved-prompt"><span class="text-sm font-medium">개선된 프롬프트</span><textarea id="managed-improved-prompt" bind:value={improvedPrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>
			{/if}
			{#if error}<p class="text-sm text-destructive" role="alert">{error}</p>{/if}
		</div>
		{#snippet footer()}
			<OutlinedButton disabled={saving} onclick={() => (editorOpen = false)}>취소</OutlinedButton>
			<PrimaryButton loading={saving} disabled={!presetName.trim() || selectedFieldCount() === 0} onclick={() => void savePreset()}>{editingId ? '수정' : '저장'}</PrimaryButton>
		{/snippet}
	</Modal>

	<Modal bind:open={deleteModalOpen} title="프리셋을 삭제하시겠습니까?" description="삭제한 프리셋은 복구할 수 없습니다." closeOnBackdrop={!deleting} onclose={cancelDelete}>
		<p class="text-sm leading-6 text-muted-foreground">'{deleteTarget?.name}' 프리셋을 삭제합니다.</p>
		{#snippet footer()}
			<OutlinedButton disabled={deleting} onclick={cancelDelete}>취소</OutlinedButton>
			<PrimaryButton loading={deleting} variant="destructive" onclick={() => void deletePreset()}><Trash2 size={16} strokeWidth={2} /><span>삭제</span></PrimaryButton>
		{/snippet}
	</Modal>

	{#if error && !editorOpen}
		<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="프리셋 처리 실패" message={error} onclose={() => (error = '')} /></div>
	{:else if success}
		<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="프리셋" message={success} onclose={() => (success = '')} /></div>
	{/if}
{/if}
