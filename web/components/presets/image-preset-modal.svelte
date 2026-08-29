<script lang="ts">
	import { Plus, Trash2 } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import Select from '../inputs/select.svelte';
	import { apiJson } from '$lib/utils/api';
	import type { AspectRatio, ImageOptions, LoraSelection, Preset, PresetValues } from '$lib/types/presets';

	type PresetField =
		| 'prompt'
		| 'negative_prompt'
		| 'checkpoint'
		| 'loras'
		| 'aspect_ratio'
		| 'cfg'
		| 'steps'
		| 'prompt_enhancement';
	type Props = {
		open?: boolean;
		preset: Preset | null;
		options: ImageOptions;
		onSaved: (preset: Preset) => void;
	};

	let { open = $bindable(false), preset, options, onSaved }: Props = $props();

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
	const fieldOptions: { key: PresetField; label: string }[] = [
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
	let saving = $state(false);
	let error = $state('');
	let checkpointOptions = $derived(options.checkpoints.map((value) => ({ value, label: value })));
	let loraOptions = $derived(options.loras.map((value) => ({ value, label: value })));

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
		const values = preset?.values ?? {};
		const fields = new Set(preset?.saved_fields ?? Object.keys(allFields));
		editingId = preset?.id ?? null;
		presetName = preset?.name ?? '';
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
	});

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

	function selectedFieldCount() {
		return fieldOptions.filter(({ key }) => selectedFields[key]).length;
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

	async function save() {
		error = '';
		if (!presetName.trim()) return (error = '프리셋 이름을 입력해 주세요.');
		if (!selectedFieldCount()) return (error = '저장할 설정을 하나 이상 선택해 주세요.');
		if (selectedFields.prompt && !prompt.trim()) return (error = '긍정 프롬프트를 입력해 주세요.');
		if (selectedFields.checkpoint && !checkpoint) return (error = '체크포인트를 선택해 주세요.');
		saving = true;
		try {
			const saved = await apiJson<Preset>(editingId ? `presets/${editingId}` : 'presets', {
				method: editingId ? 'PUT' : 'POST',
				json: { type: 't2i', name: presetName.trim(), values: buildValues() }
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
					<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted"><input type="checkbox" checked={selectedFields[field.key]} onchange={(event) => (selectedFields[field.key] = (event.currentTarget as HTMLInputElement).checked)} class="size-4 accent-primary" /><span>{field.label}</span></label>
				{/each}
			</div>
		</div>
		{#if selectedFields.prompt}<label class="block space-y-2" for="image-preset-prompt"><span class="text-sm font-medium">긍정 프롬프트</span><textarea id="image-preset-prompt" bind:value={prompt} rows="4" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if selectedFields.negative_prompt}<label class="block space-y-2" for="image-preset-negative"><span class="text-sm font-medium">부정 프롬프트</span><textarea id="image-preset-negative" bind:value={negativePrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if selectedFields.checkpoint}<Select id="image-preset-checkpoint" label="체크포인트" options={checkpointOptions} bind:value={checkpoint} autocomplete disabled={checkpointOptions.length === 0} required />{/if}
		{#if selectedFields.loras}
			<div class="space-y-3"><div class="flex items-center justify-between gap-3"><span class="text-sm font-medium">LoRA</span><button type="button" onclick={addLora} disabled={loraOptions.length === 0 || loras.length >= loraOptions.length || loras.some((lora) => !lora.name)} class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/10 disabled:pointer-events-none disabled:opacity-50"><Plus size={14} strokeWidth={2} /><span>LoRA 추가</span></button></div>
				{#each loras as lora, index (index)}<div class="rounded-lg border border-border p-3"><div class="flex items-start gap-2"><div class="min-w-0 flex-1"><Select id={`image-preset-lora-${index}`} label={`LoRA ${index + 1}`} options={availableLoraOptions(index)} bind:value={lora.name} autocomplete /></div><button type="button" aria-label={`LoRA ${index + 1} 제거`} onclick={() => removeLora(index)} class="mt-7 inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"><Trash2 size={15} strokeWidth={1.8} /></button></div>{#if lora.name}<label class="mt-3 block space-y-2" for={`image-preset-lora-strength-${index}`}><span class="text-sm font-medium">Strength</span><input id={`image-preset-lora-strength-${index}`} type="number" min="-2" max="2" step="0.05" bind:value={lora.strength} class={numberInputClass} /></label>{/if}</div>{/each}
			</div>
		{/if}
		{#if selectedFields.aspect_ratio}<Select id="image-preset-aspect" label="이미지 비율" options={aspectRatioOptions} bind:value={aspectRatio} /><div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="image-preset-width"><span class="text-sm font-medium">가로</span><input id="image-preset-width" type="number" min="64" max="2048" step="8" bind:value={width} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} /></label><label class="block space-y-2" for="image-preset-height"><span class="text-sm font-medium">세로</span><input id="image-preset-height" type="number" min="64" max="2048" step="8" bind:value={height} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} /></label></div>{/if}
		{#if selectedFields.cfg || selectedFields.steps}<div class="grid gap-4 sm:grid-cols-2">{#if selectedFields.cfg}<label class="block space-y-2" for="image-preset-cfg"><span class="text-sm font-medium">CFG</span><input id="image-preset-cfg" type="number" min="0" max="20" step="0.1" bind:value={cfg} class={numberInputClass} /></label>{/if}{#if selectedFields.steps}<label class="block space-y-2" for="image-preset-steps"><span class="text-sm font-medium">Steps</span><input id="image-preset-steps" type="number" min="1" max="100" step="1" bind:value={steps} class={numberInputClass} /></label>{/if}</div>{/if}
		{#if selectedFields.prompt_enhancement}<label class="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm"><input type="checkbox" bind:checked={promptEnhancementEnabled} class="size-4 accent-primary" /><span>프롬프트 개선 사용</span></label><label class="block space-y-2" for="image-preset-improved"><span class="text-sm font-medium">개선된 프롬프트</span><textarea id="image-preset-improved" bind:value={improvedPrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if error}<p class="text-sm text-destructive" role="alert">{error}</p>{/if}
	</div>
	{#snippet footer()}<OutlinedButton disabled={saving} onclick={() => (open = false)}>취소</OutlinedButton><PrimaryButton loading={saving} disabled={!presetName.trim() || !selectedFieldCount()} onclick={() => void save()}>{editingId ? '수정' : '저장'}</PrimaryButton>{/snippet}
</Modal>
