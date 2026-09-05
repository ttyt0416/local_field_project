<script lang="ts">
	import { Check } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import Select from '../inputs/select.svelte';
	import { apiJson } from '$lib/utils/api';
	import { filterModelFolder, modelFolders, parentModelFolder } from '$lib/utils/model-folders';
	import type { Preset, PresetValues, VideoGenerationOptions, VideoMode } from '$lib/types/presets';

	type PresetField = 'prompt' | 'mode' | 'checkpoint' | 'size' | 'duration' | 'fps' | 'seed';
	type Props = {
		open?: boolean;
		preset: Preset | null;
		initialValues?: PresetValues;
		onSaved: (preset: Preset) => void;
	};

	let { open = $bindable(false), preset, initialValues = {}, onSaved }: Props = $props();

	const numberInputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const fieldOptions: { key: PresetField; label: string }[] = [
		{ key: 'prompt', label: '프롬프트' },
		{ key: 'mode', label: '생성 방식' },
		{ key: 'checkpoint', label: 'checkpoint' },
		{ key: 'size', label: '영상 크기' },
		{ key: 'duration', label: '길이(초)' },
		{ key: 'fps', label: 'FPS' },
		{ key: 'seed', label: 'Seed' }
	];
	const videoModeOptions: { value: VideoMode; label: string }[] = [
		{ value: 'i2v', label: 'I2V' },
		{ value: 'fl2v', label: 'FL2V' },
		{ value: 'r2v', label: 'R2V' }
	];
	const allFields: Record<PresetField, boolean> = { prompt: true, mode: true, checkpoint: true, size: true, duration: true, fps: true, seed: true };

	let editingId = $state<string | null>(null);
	let presetName = $state('');
	let prompt = $state('');
	let videoMode = $state<VideoMode>('i2v');
	let checkpoint = $state('');
	let videoOptions = $state<VideoGenerationOptions>({ mode: 'i2v', checkpoints: [], default_checkpoint: '' });
	let videoOptionsLoading = $state(false);
	let videoOptionsRequestId = 0;
	let checkpointModalOpen = $state(false);
	let checkpointFolder = $state('');
	let width = $state(1344);
	let height = $state(768);
	let duration = $state(5);
	let fps = $state(24);
	let seed = $state('');
	let randomSeed = $state(true);
	let selectedFields = $state<Record<PresetField, boolean>>({ ...allFields });
	let saving = $state(false);
	let error = $state('');
	let checkpointFolders = $derived(modelFolders(videoOptions.checkpoints));
	let filteredCheckpoints = $derived(filterModelFolder(videoOptions.checkpoints, checkpointFolder));

	$effect(() => {
		if (!open) return;
		const values = preset?.values ?? initialValues;
		const fields = new Set(preset?.saved_fields ?? Object.keys(allFields));
		const hasSize = fields.has('size') || fields.has('width') || fields.has('height');
		const hasSeed = fields.has('seed') || fields.has('random_seed');
		editingId = preset?.id ?? null;
		presetName = preset?.name ?? '';
		prompt = values.prompt ?? '';
		videoMode = values.mode ?? 'i2v';
		checkpoint = values.checkpoint ?? '';
		width = values.width ?? 1344;
		height = values.height ?? 768;
		duration = values.duration ?? 5;
		fps = values.fps ?? 24;
		seed = values.seed ?? '';
		randomSeed = values.random_seed ?? !values.seed;
		selectedFields = {
			prompt: fields.has('prompt'),
			mode: fields.has('mode') || fields.has('checkpoint'),
			checkpoint: fields.has('checkpoint'),
			size: hasSize,
			duration: fields.has('duration'),
			fps: fields.has('fps'),
			seed: hasSeed
		};
		error = '';
	});

	$effect(() => {
		const mode = videoMode;
		if (open) void loadVideoOptions(mode);
	});

	async function loadVideoOptions(mode: VideoMode) {
		const requestId = ++videoOptionsRequestId;
		videoOptionsLoading = true;
		try {
			const options = await apiJson<VideoGenerationOptions>(`generation/video/options?mode=${mode}`);
			if (requestId !== videoOptionsRequestId) return;
			videoOptions = options;
			checkpoint = options.checkpoints.includes(checkpoint) ? checkpoint : options.default_checkpoint;
			checkpointFolder = '';
		} catch (reason) {
			if (requestId !== videoOptionsRequestId) return;
			videoOptions = { mode, checkpoints: [], default_checkpoint: '' };
			checkpoint = '';
			error = reason instanceof Error ? reason.message : '동영상 checkpoint 목록을 불러오지 못했습니다.';
		} finally {
			if (requestId === videoOptionsRequestId) videoOptionsLoading = false;
		}
	}

	function toggleField(key: PresetField, selected: boolean) {
		selectedFields[key] = selected;
		if (key === 'checkpoint' && selected) selectedFields.mode = true;
		if (key === 'mode' && !selected) selectedFields.checkpoint = false;
	}

	function selectedFieldCount() {
		return fieldOptions.filter(({ key }) => selectedFields[key]).length;
	}

	function buildValues(): PresetValues {
		const values: PresetValues = {};
		if (selectedFields.prompt) values.prompt = prompt.trim();
		if (selectedFields.mode) values.mode = videoMode;
		if (selectedFields.checkpoint) values.checkpoint = checkpoint;
		if (selectedFields.size) {
			values.width = width;
			values.height = height;
		}
		if (selectedFields.duration) values.duration = duration;
		if (selectedFields.fps) values.fps = fps;
		if (selectedFields.seed) {
			values.random_seed = randomSeed;
			if (!randomSeed && seed.trim()) values.seed = seed.trim();
		}
		return values;
	}

	async function save() {
		error = '';
		if (!presetName.trim()) return (error = '프리셋 이름을 입력해 주세요.');
		if (!selectedFieldCount()) return (error = '저장할 설정을 하나 이상 선택해 주세요.');
		if (selectedFields.prompt && !prompt.trim()) return (error = '프롬프트를 입력해 주세요.');
		if (selectedFields.checkpoint && (videoOptionsLoading || !videoOptions.checkpoints.includes(checkpoint))) return (error = '동영상 checkpoint를 선택해 주세요.');
		if (selectedFields.seed && !randomSeed && !seed.trim()) return (error = '시드를 입력하거나 무작위 시드를 선택해 주세요.');
		saving = true;
		try {
			const saved = await apiJson<Preset>(editingId ? `presets/${editingId}` : 'presets', {
				method: editingId ? 'PUT' : 'POST',
				json: { type: 'video', name: presetName.trim(), values: buildValues() }
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

<Modal bind:open title={editingId ? 'VIDEO GEN 프리셋 수정' : 'VIDEO GEN 프리셋 저장'} description="영상 생성 설정을 선택해 저장합니다." closeOnBackdrop={!saving}>
	<div class="space-y-5">
		<label class="block space-y-2" for="video-preset-name"><span class="text-sm font-medium">프리셋 이름</span><input id="video-preset-name" bind:value={presetName} maxlength="100" class={numberInputClass} /></label>
		<div class="space-y-3"><div class="flex items-center justify-between gap-3"><span class="text-sm font-medium">저장할 설정</span><span class="text-xs text-muted-foreground">{selectedFieldCount()}개 선택</span></div><div class="grid gap-2 sm:grid-cols-2">{#each fieldOptions as field}<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted"><input type="checkbox" checked={selectedFields[field.key]} onchange={(event) => toggleField(field.key, (event.currentTarget as HTMLInputElement).checked)} class="size-4 accent-primary" /><span>{field.label}</span></label>{/each}</div></div>
		{#if selectedFields.prompt}<label class="block space-y-2" for="video-preset-prompt"><span class="text-sm font-medium">프롬프트</span><textarea id="video-preset-prompt" bind:value={prompt} rows="4" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea></label>{/if}
		{#if selectedFields.mode}<Select id="video-preset-mode" label="생성 방식" options={videoModeOptions} bind:value={videoMode} />{/if}
		{#if selectedFields.checkpoint}<div class="space-y-2"><span class="text-sm font-medium">체크포인트</span><button type="button" onclick={() => (checkpointModalOpen = true)} disabled={videoOptionsLoading || videoOptions.checkpoints.length === 0} class="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-input bg-background px-3 py-2 text-left text-sm transition hover:bg-muted disabled:pointer-events-none disabled:opacity-50"><span class="min-w-0 truncate">{videoOptionsLoading ? '체크포인트 목록을 불러오는 중' : checkpoint || '체크포인트를 선택해 주세요'}</span><span class="shrink-0 text-xs font-semibold text-primary">선택</span></button></div>{/if}
		{#if selectedFields.size}<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-preset-width"><span class="text-sm font-medium">가로</span><input id="video-preset-width" type="number" min="32" max="1344" step="32" bind:value={width} class={numberInputClass} /></label><label class="block space-y-2" for="video-preset-height"><span class="text-sm font-medium">세로</span><input id="video-preset-height" type="number" min="32" max="1344" step="32" bind:value={height} class={numberInputClass} /></label></div>{/if}
		{#if selectedFields.duration}<label class="block space-y-2" for="video-preset-duration"><span class="text-sm font-medium">길이(초)</span><input id="video-preset-duration" type="number" step="0.1" bind:value={duration} class={numberInputClass} /></label>{/if}
		{#if selectedFields.fps}<label class="block space-y-2" for="video-preset-fps"><span class="text-sm font-medium">FPS</span><input id="video-preset-fps" type="number" min="1" max="120" step="1" bind:value={fps} class={numberInputClass} /></label>{/if}
		{#if selectedFields.seed}<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-preset-seed"><span class="text-sm font-medium">Seed</span><input id="video-preset-seed" type="number" min="0" max="9223372036854775807" step="1" bind:value={seed} disabled={randomSeed} required={!randomSeed} class={numberInputClass} /></label><label class="flex cursor-pointer items-center gap-3 self-end rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted sm:mb-0.5" for="video-preset-random-seed"><input id="video-preset-random-seed" type="checkbox" bind:checked={randomSeed} class="size-4 accent-primary" /><span>무작위 시드</span></label></div>{/if}
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
			{#each filteredCheckpoints as option (option)}<button type="button" onclick={() => { checkpoint = option; checkpointModalOpen = false; }} aria-pressed={checkpoint === option} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${checkpoint === option ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}><span>{option}</span>{#if checkpoint === option}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}</button>{/each}
		</div>
	</div>
</Modal>
