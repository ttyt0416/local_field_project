<script lang="ts">
	import { Check } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import Select from '../inputs/select.svelte';

	import { apiJson } from '$lib/utils/api';
	import { filterModelFolder, modelFolders, parentModelFolder } from '$lib/utils/model-folders';
	import { type LoraSelection, type Preset, type PresetValues, type VideoGenerationOptions, type VideoMode } from '$lib/types/presets';

	type PresetField = 'prompt' | 'mode' | 'checkpoint' | 'loras' | 'resolution' | 'duration' | 'fps' | 'steps' | 'sampling' | 'pdd' | 'seed';
	type VideoAspectRatio = '2:3' | '3:2' | '1:1' | '16:9' | '9:16';
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
		{ key: 'loras', label: 'LoRA' },
		{ key: 'resolution', label: '비율·메가픽셀' },
		{ key: 'duration', label: '길이(초)' },
		{ key: 'fps', label: 'FPS' },
		{ key: 'steps', label: 'Steps' },
		{ key: 'sampling', label: '샘플러 / 스케줄러' },
		{ key: 'pdd', label: 'PDD 사용' },
		{ key: 'seed', label: 'Seed' }
	];
	const videoModeOptions: { value: VideoMode; label: string }[] = [
		{ value: 'i2v', label: 'I2V' },
		{ value: 'fl2v', label: 'FL2V' },
		{ value: 'r2v', label: 'R2V' }
	];
	const allFields: Record<PresetField, boolean> = { prompt: true, mode: true, checkpoint: true, loras: true, resolution: true, duration: true, fps: true, steps: true, sampling: true, pdd: true, seed: true };
	const videoAspectRatioOptions: { value: VideoAspectRatio; label: string }[] = [{ value: '2:3', label: '2:3' }, { value: '3:2', label: '3:2' }, { value: '1:1', label: '1:1' }, { value: '16:9', label: '16:9' }, { value: '9:16', label: '9:16' }];

	let editingId = $state<string | null>(null);
	let presetName = $state('');
	let prompt = $state('');
	let videoMode = $state<VideoMode>('i2v');
	let checkpoint = $state('');
	let videoOptions = $state<VideoGenerationOptions>({ mode: 'i2v', checkpoints: [], default_checkpoint: '', loras: [], samplers: [], schedulers: [], default_sampler: '', default_scheduler: '', pdd_available: false, learned_upscale_available: false });
	let videoOptionsLoading = $state(false);
	let videoOptionsRequestId = 0;
	let checkpointModalOpen = $state(false);
	let checkpointFolder = $state('');
	let loraModalOpen = $state(false);
	let loraFolder = $state('');
	let loras = $state<LoraSelection[]>([]);
	let aspectRatio = $state<VideoAspectRatio>('16:9');
	let megapixels = $state(1.0);
	let learnedUpscale = $state(false);
	let targetMegapixels = $state(2.0);
	let duration = $state(5);
	let fps = $state(24);
	let steps = $state(4);
	let usePdd = $state(false);
	let samplerName = $state('');
	let scheduler = $state('');
	let samplingOpen = $state(false);

	let seed = $state('');
	let randomSeed = $state(true);
	let selectedFields = $state<Record<PresetField, boolean>>({ ...allFields });
	let saving = $state(false);
	let error = $state('');
	let checkpointFolders = $derived(modelFolders(videoOptions.checkpoints));
	let filteredCheckpoints = $derived(filterModelFolder(videoOptions.checkpoints, checkpointFolder));
	let loraFolders = $derived(modelFolders(videoOptions.loras));
	let visibleLoras = $derived(filterModelFolder(videoOptions.loras, loraFolder));


	$effect(() => {
		if (!open) return;
		const values = preset?.values ?? initialValues;
		const fields = new Set(preset?.saved_fields ?? Object.keys(allFields));
		const hasResolution = fields.has('resolution') || fields.has('aspect_ratio') || fields.has('megapixels') || fields.has('upscale_mode') || fields.has('target_megapixels') || fields.has('width') || fields.has('height');
		const hasSeed = fields.has('seed') || fields.has('random_seed');
		editingId = preset?.id ?? null;
		presetName = preset?.name ?? '';
		prompt = values.prompt ?? '';
		videoMode = values.mode ?? 'i2v';
		checkpoint = values.checkpoint ?? '';
		loras = values.loras ?? [];
		aspectRatio = values.aspect_ratio && values.aspect_ratio !== 'custom' ? values.aspect_ratio : '16:9';
		megapixels = values.megapixels ?? (values.width && values.height ? Math.floor(values.width * values.height / 100_000 + 0.5) / 10 : 1.0);
		learnedUpscale = values.upscale_mode === 'learned_3d';
		targetMegapixels = values.target_megapixels ?? 2.0;
		duration = values.duration ?? 5;
		fps = values.fps ?? 24;
		steps = values.steps ?? 4;
		usePdd = learnedUpscale ? false : values.use_pdd ?? false;
		samplerName = values.sampler_name ?? '';
		scheduler = values.scheduler ?? '';

		seed = values.seed ?? '';
		randomSeed = values.random_seed ?? !values.seed;
		selectedFields = {
			prompt: fields.has('prompt'),
			mode: fields.has('mode') || fields.has('checkpoint'),
			checkpoint: fields.has('checkpoint'),
			loras: fields.has('loras'),
			resolution: hasResolution,
			duration: fields.has('duration'),
			fps: fields.has('fps'),
			steps: fields.has('steps'),
			sampling: fields.has('sampler_name') || fields.has('scheduler') || fields.has('sampling'),
			pdd: fields.has('use_pdd'),
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
			if (!options.learned_upscale_available) learnedUpscale = false;
			checkpoint = options.checkpoints.includes(checkpoint)
				? checkpoint
				: options.default_checkpoint;
			checkpointFolder = '';
			loraFolder = '';
			loras = loras.filter((lora) => options.loras.includes(lora.name));
			samplerName = options.samplers.includes(samplerName) ? samplerName : options.default_sampler;
			scheduler = options.schedulers.includes(scheduler) ? scheduler : options.default_scheduler;
		} catch (reason) {
			if (requestId !== videoOptionsRequestId) return;
			videoOptions = { mode, checkpoints: [], default_checkpoint: '', loras: [], samplers: [], schedulers: [], default_sampler: '', default_scheduler: '', pdd_available: false, learned_upscale_available: false };
			checkpoint = '';
			loras = [];
			samplerName = '';
			scheduler = '';
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

	function toggleLora(name: string) {
		if (!videoOptions.loras.includes(name)) return;
		const selected = loras.some((lora) => lora.name === name);
		loras = selected ? loras.filter((lora) => lora.name !== name) : [...loras, { name, strength: 1 }];
	}

	function selectVideoCheckpoint(nextCheckpoint: string) {
		checkpoint = nextCheckpoint;
	}

	function setLearnedUpscale(enabled: boolean) {
		if (enabled && !videoOptions.learned_upscale_available) return;
		learnedUpscale = enabled;
		if (!enabled) return;
		usePdd = false;
		if (Number(targetMegapixels) <= Number(megapixels)) targetMegapixels = Math.floor((Number(megapixels) + 0.1) * 10 + 0.5) / 10;
	}

	function buildValues(): PresetValues {
		const values: PresetValues = {};
		if (selectedFields.prompt) values.prompt = prompt.trim();
		if (selectedFields.mode) values.mode = videoMode;
		if (selectedFields.checkpoint) values.checkpoint = checkpoint;
		if (selectedFields.loras) values.loras = loras.map(({ name, strength }) => ({ name, strength }));
		if (selectedFields.resolution) {
			values.aspect_ratio = aspectRatio;
			values.megapixels = megapixels;
			if (learnedUpscale) {
				values.upscale_mode = 'learned_3d';
				values.target_megapixels = targetMegapixels;
			}
	}
		if (selectedFields.duration) values.duration = duration;
		if (selectedFields.fps) values.fps = fps;
		if (selectedFields.steps) values.steps = steps;
		if (selectedFields.sampling) {
			values.sampler_name = samplerName;
			values.scheduler = scheduler;
		}
		if (selectedFields.pdd) values.use_pdd = learnedUpscale ? false : usePdd;

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
		if (selectedFields.resolution && learnedUpscale && !videoOptions.learned_upscale_available) return (error = 'H3 learned 3D 업스케일 model 또는 ComfyUI node를 찾을 수 없습니다.');
		if (selectedFields.resolution && learnedUpscale && Number(targetMegapixels) <= Number(megapixels)) return (error = 'Target 메가픽셀은 Base 메가픽셀보다 커야 합니다.');
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
		{#if selectedFields.loras}<div class="space-y-3"><div class="flex flex-wrap items-center justify-between gap-3"><span class="text-sm font-medium">LoRA <span class="text-xs font-normal text-muted-foreground">({loras.length})</span></span><button type="button" onclick={() => (loraModalOpen = true)} disabled={videoOptionsLoading || videoOptions.loras.length === 0} class="rounded-md px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">LoRA 선택</button></div>{#if loras.length === 0}<p class="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">사용할 LoRA가 없습니다.</p>{:else}<div class="space-y-3">{#each loras as lora (lora.name)}<div class="rounded-lg border border-border p-3"><p class="break-all text-sm font-medium">{lora.name}</p><label class="mt-3 block space-y-2" for={`video-preset-lora-strength-${lora.name}`}><span class="text-sm font-medium">Strength</span><input id={`video-preset-lora-strength-${lora.name}`} type="number" step="0.05" bind:value={lora.strength} class={numberInputClass} /></label></div>{/each}</div>{/if}</div>{/if}
		{#if selectedFields.resolution}
			<div class="grid gap-4 sm:grid-cols-2">
				<Select id="video-preset-aspect-ratio" label="영상 비율" options={videoAspectRatioOptions} bind:value={aspectRatio} />
				<label class="block space-y-2" for="video-preset-megapixels"><span class="text-sm font-medium">Base 메가픽셀</span><input id="video-preset-megapixels" type="number" min="0.1" step="0.1" bind:value={megapixels} class={numberInputClass} /></label>
			</div>
			<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted" for="video-preset-learned-upscale"><input id="video-preset-learned-upscale" type="checkbox" checked={learnedUpscale} onchange={(event) => setLearnedUpscale((event.currentTarget as HTMLInputElement).checked)} disabled={videoOptionsLoading || !videoOptions.learned_upscale_available} class="size-4 accent-primary" /><span>H3 learned 3D latent upscale</span></label>
			{#if learnedUpscale}<label class="block space-y-2" for="video-preset-target-megapixels"><span class="text-sm font-medium">Target 메가픽셀</span><input id="video-preset-target-megapixels" type="number" min="0.1" step="0.1" bind:value={targetMegapixels} class={numberInputClass} /></label>{/if}
		{/if}
		{#if selectedFields.duration}<label class="block space-y-2" for="video-preset-duration"><span class="text-sm font-medium">길이(초)</span><input id="video-preset-duration" type="number" step="0.1" bind:value={duration} class={numberInputClass} /></label>{/if}
		{#if selectedFields.fps}<label class="block space-y-2" for="video-preset-fps"><span class="text-sm font-medium">FPS</span><input id="video-preset-fps" type="number" min="1" max="120" step="1" bind:value={fps} class={numberInputClass} /></label>{/if}
		{#if selectedFields.steps}<label class="block space-y-2" for="video-preset-steps"><span class="text-sm font-medium">Steps</span><input id="video-preset-steps" type="number" min="1" max="100" step="1" bind:value={steps} class={numberInputClass} /></label>{/if}
		{#if selectedFields.sampling}<button type="button" onclick={() => (samplingOpen = true)} disabled={videoOptionsLoading || !samplerName || !scheduler} class="flex w-full items-center justify-between gap-4 rounded-lg border border-border px-3 py-3 text-left transition hover:bg-muted disabled:pointer-events-none disabled:opacity-50"><span class="text-sm font-medium">샘플러 / 스케줄러</span><span class="min-w-0 truncate text-xs text-muted-foreground">{samplerName} / {scheduler}</span></button>{/if}
		{#if selectedFields.pdd}<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted" for="video-preset-use-pdd"><input id="video-preset-use-pdd" type="checkbox" bind:checked={usePdd} disabled={learnedUpscale} class="size-4 accent-primary" /><span>PDD 사용</span></label>{/if}
		{#if selectedFields.seed}<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-preset-seed"><span class="text-sm font-medium">Seed</span><input id="video-preset-seed" type="number" min="0" max="9223372036854775807" step="1" bind:value={seed} disabled={randomSeed} required={!randomSeed} class={numberInputClass} /></label><label class="flex cursor-pointer items-center gap-3 self-end rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted sm:mb-0.5" for="video-preset-random-seed"><input id="video-preset-random-seed" type="checkbox" bind:checked={randomSeed} class="size-4 accent-primary" /><span>무작위 시드</span></label></div>{/if}
		{#if error}<p class="text-sm text-destructive" role="alert">{error}</p>{/if}
	</div>
	{#snippet footer()}<OutlinedButton disabled={saving} onclick={() => (open = false)}>취소</OutlinedButton><PrimaryButton loading={saving} disabled={!presetName.trim() || !selectedFieldCount()} onclick={() => void save()}>{editingId ? '수정' : '저장'}</PrimaryButton>{/snippet}
</Modal>

<Modal bind:open={samplingOpen} title="샘플러 / 스케줄러" description="현재 ComfyUI에서 지원하는 값을 선택하세요.">
	<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-preset-sampler"><span class="text-sm font-medium">샘플러</span><select id="video-preset-sampler" bind:value={samplerName} class={numberInputClass}>{#each videoOptions.samplers as option}<option value={option}>{option}</option>{/each}</select></label><label class="block space-y-2" for="video-preset-scheduler"><span class="text-sm font-medium">스케줄러</span><select id="video-preset-scheduler" bind:value={scheduler} class={numberInputClass}>{#each videoOptions.schedulers as option}<option value={option}>{option}</option>{/each}</select></label></div>
	{#snippet footer()}<PrimaryButton onclick={() => (samplingOpen = false)}>선택 완료</PrimaryButton>{/snippet}
</Modal>

<Modal bind:open={checkpointModalOpen} title="체크포인트 선택" description="전체 또는 하위 folder에서 하나를 선택하세요.">
	<div class="space-y-3">
		<div class="flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="체크포인트 folder filter">
			<OutlinedButton class="min-h-9 px-3 text-xs" active={checkpointFolder === ''} onclick={() => (checkpointFolder = '')}>전체</OutlinedButton>
			{#if checkpointFolder}<OutlinedButton class="min-h-9 px-3 text-xs" onclick={() => (checkpointFolder = parentModelFolder(checkpointFolder))}>바로 위 폴더</OutlinedButton>{/if}
			{#each checkpointFolders as folder}<OutlinedButton class="min-h-9 px-3 text-xs" active={checkpointFolder === folder} onclick={() => (checkpointFolder = folder)}>{folder}</OutlinedButton>{/each}
		</div>
		<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
			{#each filteredCheckpoints as option (option)}<button type="button" onclick={() => { selectVideoCheckpoint(option); checkpointModalOpen = false; }} aria-pressed={checkpoint === option} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${checkpoint === option ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}><span>{option}</span>{#if checkpoint === option}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}</button>{/each}
		</div>
	</div>
</Modal>

<Modal bind:open={loraModalOpen} title="LoRA 선택" description="동영상 LoRA를 선택할 수 있습니다.">
	<div class="space-y-3">
		<div class="flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="동영상 LoRA folder filter">
			<OutlinedButton class="min-h-9 px-3 text-xs" active={loraFolder === ''} onclick={() => (loraFolder = '')}>전체</OutlinedButton>
			{#if loraFolder}<OutlinedButton class="min-h-9 px-3 text-xs" onclick={() => (loraFolder = parentModelFolder(loraFolder))}>바로 위 폴더</OutlinedButton>{/if}
			{#each loraFolders as folder}<OutlinedButton class="min-h-9 px-3 text-xs" active={loraFolder === folder} onclick={() => (loraFolder = folder)}>{folder}</OutlinedButton>{/each}
		</div>
		<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
			{#each visibleLoras as value}
				{@const selected = loras.some((lora) => lora.name === value)}
				<button type="button" onclick={() => toggleLora(value)} aria-pressed={selected} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${selected ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}><span>{value}</span>{#if selected}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}</button>
			{/each}
		</div>
	</div>
	{#snippet footer()}<PrimaryButton onclick={() => (loraModalOpen = false)}>선택 완료</PrimaryButton>{/snippet}
</Modal>
