<script lang="ts">
	import { Check, Trash2 } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import Select from '../inputs/select.svelte';
	import SamplingSelectionModal from './sampling-selection-modal.svelte';
	import { apiJson } from '$lib/utils/api';
	import type { AspectRatio, ImageOptions, ImagePresetType, LoraSelection, Preset, PresetValues } from '$lib/types/presets';
	import { filterModelFolder, modelFolders, parentModelFolder } from '$lib/utils/model-folders';

	type PresetField =
		| 'positive_prompt_prefix'
		| 'prompt'
		| 'negative_prompt_prefix'
		| 'negative_prompt'
		| 'checkpoint'
		| 'loras'
		| 'aspect_ratio'
		| 'denoise'
		| 'cfg'
		| 'steps'
		| 'sampling'
		| 'seed'
		| 'prompt_enhancement';
	type Props = {
		open?: boolean;
		preset: Preset | null;
		initialValues?: PresetValues;
		presetType: ImagePresetType;
		options: ImageOptions;
		onSaved: (preset: Preset) => void;
	};

	let { open = $bindable(false), preset, initialValues = {}, presetType, options, onSaved }: Props = $props();
	let isI2I = $derived(presetType.startsWith('i2i_'));
	let isT2I = $derived(!isI2I);
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
	const fieldOptions: { key: PresetField; label: string }[] = [
		{ key: 'positive_prompt_prefix', label: '긍정 프롬프트 Prefix' },
		{ key: 'prompt', label: '긍정 프롬프트' },
		{ key: 'negative_prompt_prefix', label: '부정 프롬프트 Prefix' },
		{ key: 'negative_prompt', label: '부정 프롬프트' },
		{ key: 'checkpoint', label: '체크포인트' },
		{ key: 'loras', label: 'LoRA' },
		{ key: 'aspect_ratio', label: '이미지 비율·크기' },
		{ key: 'denoise', label: 'Denoise' },
		{ key: 'cfg', label: 'CFG' },
		{ key: 'steps', label: 'Steps' },
		{ key: 'sampling', label: '샘플러 / 스케줄러' },
		{ key: 'seed', label: 'Seed' },
		{ key: 'prompt_enhancement', label: '프롬프트 개선 설정' }
	];
	const allFields: Record<PresetField, boolean> = {
		positive_prompt_prefix: true,
		prompt: true,
		negative_prompt_prefix: true,
		negative_prompt: true,
		checkpoint: true,
		loras: true,
		aspect_ratio: true,
		denoise: true,
		cfg: true,
		steps: true,
		sampling: true,
		seed: true,
		prompt_enhancement: true
	};

	let editingId = $state<string | null>(null);
	let presetName = $state('');
	let positivePromptPrefix = $state('');
	let prompt = $state('');
	let negativePromptPrefix = $state('');
	let negativePrompt = $state('');
	let promptEnhancementEnabled = $state(false);
	let improvedPrompt = $state('');
	let checkpoint = $state('');
	let loras = $state<LoraSelection[]>([]);
	let aspectRatio = $state<AspectRatio>('custom');
	let width = $state(1024);
	let height = $state(1024);
	let denoise = $state(0.65);
	let cfg = $state(4);
	let steps = $state(30);
	let samplerName = $state('');
	let scheduler = $state('');
	let samplingOpen = $state(false);
	let checkpointModalOpen = $state(false);
	let loraModalOpen = $state(false);
	let checkpointFolder = $state('');
	let loraFolder = $state('');
	let seed = $state('');
	let randomSeed = $state(true);
	let selectedFields = $state<Record<PresetField, boolean>>({ ...allFields });
	let saving = $state(false);
	let error = $state('');
	let checkpointFolders = $derived(modelFolders(options.checkpoints));
	let loraFolders = $derived(modelFolders(options.loras));
	let visibleCheckpoints = $derived(filterModelFolder(options.checkpoints, checkpointFolder));
	let visibleLoras = $derived(filterModelFolder(options.loras, loraFolder));

	$effect(() => {
		if (!open) return;
		const size = aspectRatioPresets[aspectRatio];
		if (size) {
			width = size.width;
			height = size.height;
		}
	});

	$effect(() => {
		if (!open) return;
		const values = preset?.values ?? initialValues;
		const fields = new Set(preset?.saved_fields ?? Object.keys(allFields));
		editingId = preset?.id ?? null;
		presetName = preset?.name ?? '';
		positivePromptPrefix = values.positive_prompt_prefix ?? '';
		prompt = values.prompt ?? '';
		negativePromptPrefix = values.negative_prompt_prefix ?? '';
		negativePrompt = values.negative_prompt ?? '';
		promptEnhancementEnabled = values.prompt_enhancement_enabled ?? false;
		improvedPrompt = values.improved_prompt ?? '';
		checkpoint = values.checkpoint ?? options.default_checkpoint;
		loras = values.loras?.map(({ name, strength }) => ({ name, strength })) ?? [];
		aspectRatio = values.aspect_ratio ?? 'custom';
		width = values.width ?? 1024;
		height = values.height ?? 1024;
		denoise = values.denoise ?? 0.65;
		cfg = values.cfg ?? 4;
		steps = values.steps ?? 30;
		samplerName = values.sampler_name ?? options.default_sampler;
		scheduler = values.scheduler ?? options.default_scheduler;
		seed = values.seed ?? '';
		randomSeed = values.random_seed ?? !values.seed;
		selectedFields = {
			positive_prompt_prefix: fields.has('positive_prompt_prefix'),
			prompt: fields.has('prompt'),
			negative_prompt_prefix: fields.has('negative_prompt_prefix'),
			negative_prompt: fields.has('negative_prompt'),
			checkpoint: fields.has('checkpoint'),
			loras: fields.has('loras'),
			aspect_ratio: fields.has('aspect_ratio'),
			denoise: isI2I && fields.has('denoise'),
			cfg: fields.has('cfg'),
			steps: fields.has('steps'),
			sampling: fields.has('sampler_name') || fields.has('scheduler') || fields.has('sampling'),
			seed: fields.has('seed') || fields.has('random_seed'),
			prompt_enhancement: isT2I && (fields.has('prompt_enhancement_enabled') || fields.has('improved_prompt'))
		};
		checkpointFolder = '';
		loraFolder = '';
		error = '';
	});

	function toggleLora(name: string) {
		const selected = loras.some((lora) => lora.name === name);
		loras = selected ? loras.filter((lora) => lora.name !== name) : [...loras, { name, strength: 1.0 }];
	}

	function removeLora(index: number) {
		loras = loras.filter((_, currentIndex) => currentIndex !== index);
	}

	function selectedFieldCount() {
		return fieldOptions
			.filter(({ key }) => (key === 'denoise' ? isI2I : key === 'prompt_enhancement' ? isT2I : true))
			.filter(({ key }) => selectedFields[key]).length;
	}

	function buildValues(): PresetValues {
		const values: PresetValues = {};
		if (selectedFields.positive_prompt_prefix) values.positive_prompt_prefix = positivePromptPrefix.trim();
		if (selectedFields.prompt) values.prompt = prompt.trim();
		if (selectedFields.negative_prompt_prefix) values.negative_prompt_prefix = negativePromptPrefix.trim();
		if (selectedFields.negative_prompt) values.negative_prompt = negativePrompt.trim();
		if (selectedFields.checkpoint) values.checkpoint = checkpoint;
		if (selectedFields.loras) values.loras = loras.filter(({ name }) => name.trim()).map(({ name, strength }) => ({ name, strength }));
		if (selectedFields.aspect_ratio) {
			values.aspect_ratio = aspectRatio;
			values.width = width;
			values.height = height;
		}
		if (isI2I && selectedFields.denoise) values.denoise = denoise;
		if (selectedFields.cfg) values.cfg = cfg;
		if (selectedFields.steps) values.steps = steps;
		if (selectedFields.sampling) {
			values.sampler_name = samplerName;
			values.scheduler = scheduler;
		}
		if (selectedFields.seed) {
			values.random_seed = randomSeed;
			if (!randomSeed && seed.trim()) values.seed = seed.trim();
		}
		if (isT2I && selectedFields.prompt_enhancement) {
			values.prompt_enhancement_enabled = promptEnhancementEnabled;
			if (improvedPrompt.trim()) values.improved_prompt = improvedPrompt.trim();
		}
		return values;
	}

	async function save() {
		error = '';
		if (!presetName.trim()) return (error = '프리셋 이름을 입력해 주세요.');
		if (!selectedFieldCount()) return (error = '저장할 설정을 하나 이상 선택해 주세요.');
		if (selectedFields.prompt && !prompt.trim()) return (error = '긍정 프롬프트를 입력해 주세요.');
		if (selectedFields.checkpoint && !checkpoint) return (error = '체크포인트를 선택해 주세요.');
		if (isI2I && selectedFields.denoise && (!Number.isFinite(denoise) || denoise < 0 || denoise > 1)) return (error = 'Denoise는 0.0에서 1.0 사이로 입력해 주세요.');
		if (selectedFields.seed && !randomSeed && !seed.trim()) return (error = '시드를 입력하거나 무작위 시드를 선택해 주세요.');
		saving = true;
		try {
			const saved = await apiJson<Preset>(editingId ? `presets/${editingId}` : 'presets', {
				method: editingId ? 'PUT' : 'POST',
				json: { type: presetType, name: presetName.trim(), values: buildValues() }
			});
			open = false;
			onSaved(saved);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '프리셋을 저장하지 못했습니다.';
		} finally {
			saving = false;
		}
	}
</script>

<Modal bind:open title={editingId ? 'IMAGE GEN 프리셋 수정' : 'IMAGE GEN 프리셋 저장'} description="이미지 생성 설정을 선택해 저장합니다." closeOnBackdrop={!saving}>
	<div class="space-y-5">
		<label class="block space-y-2" for="image-preset-name"><span class="text-sm font-medium">프리셋 이름</span><input id="image-preset-name" bind:value={presetName} maxlength="100" class={numberInputClass} /></label>
		<div class="space-y-3">
			<div class="flex items-center justify-between gap-3"><span class="text-sm font-medium">저장할 설정</span><span class="text-xs text-muted-foreground">{selectedFieldCount()}개 선택</span></div>
			<div class="grid gap-2 sm:grid-cols-2">
				{#each fieldOptions as field}
					{#if field.key === 'denoise' ? isI2I : field.key === 'prompt_enhancement' ? isT2I : true}
						<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted"><input type="checkbox" checked={selectedFields[field.key]} onchange={(event) => (selectedFields[field.key] = (event.currentTarget as HTMLInputElement).checked)} class="size-4 accent-primary" /><span>{field.label}</span></label>
					{/if}
				{/each}
			</div>
		</div>
		{#if selectedFields.positive_prompt_prefix}<label class="block space-y-2" for="image-preset-positive-prefix"><span class="text-sm font-medium">긍정 프롬프트 Prefix</span><textarea id="image-preset-positive-prefix" bind:value={positivePromptPrefix} rows="2" maxlength="5000" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if selectedFields.prompt}<label class="block space-y-2" for="image-preset-prompt"><span class="text-sm font-medium">긍정 프롬프트</span><textarea id="image-preset-prompt" bind:value={prompt} rows="4" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if selectedFields.negative_prompt_prefix}<label class="block space-y-2" for="image-preset-negative-prefix"><span class="text-sm font-medium">부정 프롬프트 Prefix</span><textarea id="image-preset-negative-prefix" bind:value={negativePromptPrefix} rows="2" maxlength="5000" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if selectedFields.negative_prompt}<label class="block space-y-2" for="image-preset-negative"><span class="text-sm font-medium">부정 프롬프트</span><textarea id="image-preset-negative" bind:value={negativePrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if selectedFields.checkpoint}<div class="space-y-2"><span class="text-sm font-medium">체크포인트</span><button type="button" onclick={() => (checkpointModalOpen = true)} disabled={options.checkpoints.length === 0} class="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-input bg-background px-3 py-2 text-left text-sm transition hover:bg-muted disabled:pointer-events-none disabled:opacity-50"><span class="min-w-0 truncate">{checkpoint || '체크포인트를 선택해 주세요'}</span><span class="shrink-0 text-xs font-semibold text-primary">선택</span></button></div>{/if}
		{#if selectedFields.loras}
			<div class="space-y-3"><div class="flex items-center justify-between gap-3"><span class="text-sm font-medium">LoRA <span class="text-xs font-normal text-muted-foreground">({loras.length})</span></span><button type="button" onclick={() => (loraModalOpen = true)} disabled={options.loras.length === 0} class="rounded-md px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">LoRA 선택</button></div>
				{#if loras.length === 0}<p class="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">사용할 LoRA가 없습니다.</p>{:else}{#each loras as lora, index (lora.name)}<div class="rounded-lg border border-border p-3"><div class="flex items-start gap-2"><p class="min-w-0 flex-1 break-all text-sm font-medium">{lora.name}</p><button type="button" aria-label={`${lora.name} 제거`} onclick={() => removeLora(index)} class="inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"><Trash2 size={15} strokeWidth={1.8} /></button></div><label class="mt-3 block space-y-2" for={`image-preset-lora-strength-${index}`}><span class="text-sm font-medium">Strength</span><input id={`image-preset-lora-strength-${index}`} type="number" step="0.05" bind:value={lora.strength} class={numberInputClass} /></label></div>{/each}{/if}
			</div>
		{/if}
		{#if selectedFields.aspect_ratio}<Select id="image-preset-aspect" label="이미지 비율" options={aspectRatioOptions} bind:value={aspectRatio} /><div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="image-preset-width"><span class="text-sm font-medium">가로</span><input id="image-preset-width" type="number" min="64" max="2048" step="8" bind:value={width} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} /></label><label class="block space-y-2" for="image-preset-height"><span class="text-sm font-medium">세로</span><input id="image-preset-height" type="number" min="64" max="2048" step="8" bind:value={height} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} /></label></div>{/if}
		{#if isI2I && selectedFields.denoise}<label class="block space-y-2" for="image-preset-denoise"><span class="text-sm font-medium">Denoise</span><input id="image-preset-denoise" type="number" min="0" max="1" step="0.05" bind:value={denoise} class={numberInputClass} /></label>{/if}
		{#if selectedFields.cfg || selectedFields.steps}<div class="grid gap-4 sm:grid-cols-2">{#if selectedFields.cfg}<label class="block space-y-2" for="image-preset-cfg"><span class="text-sm font-medium">CFG</span><input id="image-preset-cfg" type="number" min="0" max="20" step="0.1" bind:value={cfg} class={numberInputClass} /></label>{/if}{#if selectedFields.steps}<label class="block space-y-2" for="image-preset-steps"><span class="text-sm font-medium">Steps</span><input id="image-preset-steps" type="number" min="1" max="100" step="1" bind:value={steps} class={numberInputClass} /></label>{/if}</div>{/if}
		{#if selectedFields.sampling}<button type="button" onclick={() => (samplingOpen = true)} class="flex w-full items-center justify-between gap-4 rounded-lg border border-border px-3 py-3 text-left transition hover:bg-muted"><span class="text-sm font-medium">샘플러 / 스케줄러</span><span class="min-w-0 truncate text-xs text-muted-foreground">{samplerName} / {scheduler}</span></button>{/if}
		{#if selectedFields.seed}<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="image-preset-seed"><span class="text-sm font-medium">Seed</span><input id="image-preset-seed" type="number" min="0" max="9223372036854775807" step="1" bind:value={seed} disabled={randomSeed} required={!randomSeed} class={numberInputClass} /></label><label class="flex cursor-pointer items-center gap-3 self-end rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted sm:mb-0.5" for="image-preset-random-seed"><input id="image-preset-random-seed" type="checkbox" bind:checked={randomSeed} class="size-4 accent-primary" /><span>무작위 시드</span></label></div>{/if}
		{#if isT2I && selectedFields.prompt_enhancement}<label class="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm"><input type="checkbox" bind:checked={promptEnhancementEnabled} class="size-4 accent-primary" /><span>프롬프트 개선 사용</span></label><label class="block space-y-2" for="image-preset-improved"><span class="text-sm font-medium">개선된 프롬프트</span><textarea id="image-preset-improved" bind:value={improvedPrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if error}<p class="text-sm text-destructive" role="alert">{error}</p>{/if}
	</div>
	{#snippet footer()}<OutlinedButton disabled={saving} onclick={() => (open = false)}>취소</OutlinedButton><PrimaryButton loading={saving} disabled={!presetName.trim() || !selectedFieldCount()} onclick={() => void save()}>{editingId ? '수정' : '저장'}</PrimaryButton>{/snippet}
</Modal>

<Modal bind:open={checkpointModalOpen} title="체크포인트 선택" description="전체 또는 하위 folder에서 하나를 선택하세요.">
	<div class="space-y-3">
		<div class="flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="체크포인트 folder filter">
			<OutlinedButton class="min-h-9 px-3 text-xs" active={checkpointFolder === ''} onclick={() => (checkpointFolder = '')}>전체</OutlinedButton>
			{#if checkpointFolder}<OutlinedButton class="min-h-9 px-3 text-xs" onclick={() => (checkpointFolder = parentModelFolder(checkpointFolder))}>바로 위 폴더</OutlinedButton>{/if}
			{#each checkpointFolders as folder}<OutlinedButton class="min-h-9 px-3 text-xs" active={checkpointFolder === folder} onclick={() => (checkpointFolder = folder)}>{folder}</OutlinedButton>{/each}
		</div>
		<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
			{#each visibleCheckpoints as value}<button type="button" onclick={() => { checkpoint = value; checkpointModalOpen = false; }} aria-pressed={checkpoint === value} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${checkpoint === value ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}><span>{value}</span>{#if checkpoint === value}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}</button>{/each}
		</div>
	</div>
</Modal>

<Modal bind:open={loraModalOpen} title="LoRA 선택" description="전체 또는 하위 folder에서 선택하세요.">
	<div class="space-y-3">
		<div class="flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="LoRA folder filter">
			<OutlinedButton class="min-h-9 px-3 text-xs" active={loraFolder === ''} onclick={() => (loraFolder = '')}>전체</OutlinedButton>
			{#if loraFolder}<OutlinedButton class="min-h-9 px-3 text-xs" onclick={() => (loraFolder = parentModelFolder(loraFolder))}>바로 위 폴더</OutlinedButton>{/if}
			{#each loraFolders as folder}<OutlinedButton class="min-h-9 px-3 text-xs" active={loraFolder === folder} onclick={() => (loraFolder = folder)}>{folder}</OutlinedButton>{/each}
		</div>
		<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
			{#each visibleLoras as value}{@const selected = loras.some((lora) => lora.name === value)}<button type="button" onclick={() => toggleLora(value)} aria-pressed={selected} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${selected ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}><span>{value}</span>{#if selected}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}</button>{/each}
		</div>
	</div>
	{#snippet footer()}<PrimaryButton onclick={() => (loraModalOpen = false)}>선택 완료</PrimaryButton>{/snippet}
</Modal>

<SamplingSelectionModal
	bind:open={samplingOpen}
	samplers={options.samplers}
	schedulers={options.schedulers}
	bind:samplerName
	bind:scheduler
/>
