<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ArrowLeftRight, Check, FolderOpen, ImagePlus, Save, Sparkles, X } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import Modal from '../../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Select from '../../../../components/inputs/select.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import SamplingSelectionModal from '../../../../components/presets/sampling-selection-modal.svelte';
	import { SERVER_URL } from '$lib/configs/constants';
	import { apiJson } from '$lib/utils/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { imageGenerationStore, type ImageGenerationParameters } from '$lib/stores/image-generation.svelte';
	import { formatElapsedSeconds } from '$lib/utils/generation';
	import { filterModelFolder, modelFolders, parentModelFolder } from '$lib/utils/model-folders';

	type ModelFamily = 'anima' | 'illustrious';
	type ModelFamilyTab = ModelFamily | 'krea2';
	type ImageOptions = {
		model_family: ModelFamily;
		checkpoints: string[];
		loras: string[];
		embeddings: string[];
		samplers: string[];
		schedulers: string[];
		default_checkpoint: string;
		default_sampler: string;
		default_scheduler: string;
	};

	type LoraSelection = {
		name: string;
		strength: number;
	};

	type PresetField =
		| 'prompt'
		| 'negative_prompt'
		| 'checkpoint'
		| 'loras'
		| 'aspect_ratio'
		| 'cfg'
		| 'steps'
		| 'sampling'
		| 'seed'
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
		sampler_name?: string;
		scheduler?: string;
		seed?: string;
		random_seed?: boolean;
	};
	type Preset = {
		id: string;
		type: 't2i_anima' | 't2i_illustrious';
		name: string;
		values: PresetValues;
		is_default: boolean;
		saved_fields: string[];
		created_at: string;
		updated_at: string;
	};
	type PresetSaveMode = 'new' | 'overwrite';

	type AspectRatio = 'custom' | '2:3' | '3:2' | '1:1' | '16:9' | '9:16';
	type ImageSize = { width: number; height: number };

	const modelFamily: ModelFamily = page.url.searchParams.get('family') === 'illustrious' ? 'illustrious' : 'anima';
	const presetType: Preset['type'] = modelFamily === 'illustrious' ? 't2i_illustrious' : 't2i_anima';
	const familyLabel = modelFamily === 'illustrious' ? 'Illustrious' : 'Anima';
	const pageTitle = 'T2I';
	// ponytail: Krea2 stays generator-option-only until its workflow and request validation exist.
	const modelFamilyTabs: { value: ModelFamilyTab; label: string; disabled?: boolean }[] = [
		{ value: 'anima', label: 'ANIMA' },
		{ value: 'illustrious', label: 'ILLUSTRIOUS' },
		{ value: 'krea2', label: 'KREA2', disabled: true }
	];
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
	const aspectRatioPresets: Record<AspectRatio, ImageSize | null> = {
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
		{ key: 'sampling', label: '샘플러 / 스케줄러' },
		{ key: 'seed', label: 'Seed' },
		{ key: 'prompt_enhancement', label: '프롬프트 개선 설정' }
	];
	const defaultPresetFieldSelection: Record<PresetField, boolean> = {
		prompt: true,
		negative_prompt: true,
		checkpoint: true,
		loras: true,
		aspect_ratio: true,
		cfg: true,
		steps: true,
		sampling: true,
		seed: true,
		prompt_enhancement: true
	};

	let active = true;
	let ready = $state(false);
	let optionsLoading = $state(true);
	let optionsError = $state('');
	let generationError = $state('');
	let promptEnhancementError = $state('');
	let successMessage = $state('');
	let generating = $state(false);
	let cancelling = $state(false);
	let enhancingPrompt = $state(false);
	let generationStatus = $state('');
	let progress = $state(0);
	let queuePosition = $state<number | null>(null);
	let elapsedSeconds = $state(0);
	let promptId = $state('');
	let imageUrl = $state('');
	let generationId = $state('');
	let imageJobKey = $state('');
	let announcedTerminal = $state('');
	let presets = $state<Preset[]>([]);
	let presetsLoading = $state(false);
	let savingPreset = $state(false);
	let presetError = $state('');
	let presetSuccess = $state('');
	let presetName = $state('');
	let savePresetModalOpen = $state(false);
	let loadPresetModalOpen = $state(false);
	let selectedPresetFields = $state<Record<PresetField, boolean>>({ ...defaultPresetFieldSelection });
	let presetSaveMode = $state<PresetSaveMode>('new');
	let overwritePresetId = $state('');
	let options = $state<ImageOptions>({
		model_family: modelFamily,
		checkpoints: [],
		loras: [],
		embeddings: [],
		samplers: [],
		schedulers: [],
		default_checkpoint: '',
		default_sampler: '',
		default_scheduler: ''
	});
	let prompt = $state('');
	let promptEnhancementEnabled = $state(false);
	let improvedPrompt = $state('');
	let negativePrompt = $state(defaultNegativePrompt);
	let checkpoint = $state('');
	let loras = $state<LoraSelection[]>([]);
	let cfg = $state(4);
	let steps = $state(30);
	let samplerName = $state('');
	let scheduler = $state('');
	let samplingModalOpen = $state(false);
	let checkpointModalOpen = $state(false);
	let loraModalOpen = $state(false);
	let checkpointFolder = $state('');
	let loraFolder = $state('');
	let embeddingFolder = $state('');
	let checkpointFolders = $derived(modelFolders(options.checkpoints));
	let loraFolders = $derived(modelFolders(options.loras));
	let embeddingFolders = $derived(modelFolders(options.embeddings));
	let visibleCheckpoints = $derived(filterModelFolder(options.checkpoints, checkpointFolder));
	let visibleLoras = $derived(filterModelFolder(options.loras, loraFolder));
	let visibleEmbeddings = $derived(filterModelFolder(options.embeddings, embeddingFolder));
	let embeddingModalOpen = $state(false);
	let embeddingTarget = $state<'positive' | 'negative'>('positive');
	let seed = $state('');
	let randomSeed = $state(true);
	let aspectRatio = $state<AspectRatio>('custom');
	let width = $state(1024);
	let height = $state(1024);

	let explicitAspectSize: ImageSize | null = null;

	$effect(() => {
		const preset = aspectRatioPresets[aspectRatio];
		if (!preset) return;
		const size = explicitAspectSize;
		explicitAspectSize = null;
		if (size) {
			width = size.width;
			height = size.height;
			return;
		}
		width = preset.width;
		height = preset.height;
	});

	function toggleLora(name: string) {
		const selected = loras.some((lora) => lora.name === name);
		if (!selected && loras.length >= 8) {
			generationError = 'LoRA는 최대 8개까지 선택할 수 있습니다.';
			return;
		}
		loras = selected ? loras.filter((lora) => lora.name !== name) : [...loras, { name, strength: 1.0 }];
	}

	function openEmbeddingPicker(target: 'positive' | 'negative') {
		embeddingTarget = target;
		embeddingModalOpen = true;
	}

	function insertEmbedding(name: string) {
		const token = `embedding:${name.replace(/\.(safetensors|pt|bin)$/i, '')}`;
		const current = embeddingTarget === 'positive' ? prompt : negativePrompt;
		if (current.includes(token)) {
			embeddingModalOpen = false;
			return;
		}
		const next = current.trim() ? `${current.trim()}, ${token}` : token;
		if (next.length > 5000) {
			generationError = 'Embedding을 추가하면 프롬프트 길이 제한을 초과합니다.';
			return;
		}
		if (embeddingTarget === 'positive') prompt = next;
		else negativePrompt = next;
		embeddingModalOpen = false;
	}

	function selectedPresetFieldCount() {
		return presetFieldOptions.filter(({ key }) => selectedPresetFields[key]).length;
	}

	function setPresetField(key: PresetField, checked: boolean) {
		selectedPresetFields[key] = checked;
	}

	async function openSavePreset() {
		presetName = '';
		presetError = '';
		selectedPresetFields = { ...defaultPresetFieldSelection };
		presetSaveMode = 'new';
		overwritePresetId = '';
		savePresetModalOpen = true;
		presetsLoading = true;
		try {
			presets = await apiJson<Preset[]>(`presets?type=${presetType}`);
		} catch (error) {
			presetError = getErrorMessage(error);
			presets = [];
		} finally {
			presetsLoading = false;
		}
	}

	async function openLoadPreset() {
		loadPresetModalOpen = true;
		presetsLoading = true;
		presetError = '';
		try {
			presets = await apiJson<Preset[]>(`presets?type=${presetType}`);
		} catch (error) {
			presetError = getErrorMessage(error);
			presets = [];
		} finally {
			presetsLoading = false;
		}
	}

	function buildPresetValues(): PresetValues {
		const values: PresetValues = {};
		if (selectedPresetFields.prompt) values.prompt = prompt.trim();
		if (selectedPresetFields.negative_prompt) values.negative_prompt = negativePrompt.trim();
		if (selectedPresetFields.checkpoint) values.checkpoint = checkpoint;
		if (selectedPresetFields.loras) {
			values.loras = loras.filter(({ name }) => name.trim()).map(({ name, strength }) => ({ name, strength }));
		}
		if (selectedPresetFields.aspect_ratio) {
			values.aspect_ratio = aspectRatio;
			values.width = width;
			values.height = height;
		}
		if (selectedPresetFields.cfg) values.cfg = cfg;
		if (selectedPresetFields.steps) values.steps = steps;
		if (selectedPresetFields.sampling) {
			values.sampler_name = samplerName;
			values.scheduler = scheduler;
		}
		if (selectedPresetFields.seed) {
			values.random_seed = randomSeed;
			if (!randomSeed && seed.trim()) values.seed = seed.trim();
		}
		if (selectedPresetFields.prompt_enhancement) {
			values.prompt_enhancement_enabled = promptEnhancementEnabled;
			if (improvedPrompt.trim()) values.improved_prompt = improvedPrompt.trim();
		}
		return values;
	}

	async function savePreset() {
		presetError = '';
		if (!presetName.trim()) {
			presetError = '프리셋 이름을 입력해 주세요.';
			return;
		}
		if (selectedPresetFieldCount() === 0) {
			presetError = '저장할 설정을 하나 이상 선택해 주세요.';
			return;
		}
		if (selectedPresetFields.prompt && !prompt.trim()) {
			presetError = '긍정 프롬프트를 입력해 주세요.';
			return;
		}
		if (selectedPresetFields.checkpoint && !checkpoint) {
			presetError = '체크포인트를 선택해 주세요.';
			return;
		}
		if (presetSaveMode === 'overwrite' && !overwritePresetId) {
			presetError = '덮어쓸 프리셋을 선택해 주세요.';
			return;
		}
		savingPreset = true;
		try {
			await apiJson<Preset>(presetSaveMode === 'overwrite' ? `presets/${overwritePresetId}` : 'presets', {
				method: presetSaveMode === 'overwrite' ? 'PUT' : 'POST',
				json: {
					type: presetType,
					name: presetName.trim(),
					values: buildPresetValues()
				}
			});
			savePresetModalOpen = false;
			presetSuccess =
				presetSaveMode === 'overwrite'
					? `'${presetName.trim()}' 프리셋을 덮어썼습니다.`
					: `'${presetName.trim()}' 프리셋을 새로 저장했습니다.`;
		} catch (error) {
			presetError = getErrorMessage(error);
		} finally {
			savingPreset = false;
		}
	}

	function applyPreset(preset: Preset, announce = false) {
		const values = preset.values;
		if (values.prompt !== undefined) prompt = values.prompt;
		if (values.negative_prompt !== undefined) negativePrompt = values.negative_prompt;
		if (values.prompt_enhancement_enabled !== undefined) promptEnhancementEnabled = values.prompt_enhancement_enabled;
		if (values.improved_prompt !== undefined) {
			improvedPrompt = values.improved_prompt;
		}
		if (values.checkpoint !== undefined && options.checkpoints.includes(values.checkpoint)) checkpoint = values.checkpoint;
		if (values.loras !== undefined) {
			loras = values.loras.filter(({ name }) => options.loras.includes(name)).map(({ name, strength }) => ({ name, strength }));
		}
		if (values.aspect_ratio !== undefined) aspectRatio = values.aspect_ratio;
		if (values.width !== undefined) width = values.width;
		if (values.height !== undefined) height = values.height;
		if (values.width !== undefined || values.height !== undefined) {
			explicitAspectSize = { width, height };
		}
		if (values.cfg !== undefined) cfg = values.cfg;
		if (values.steps !== undefined) steps = values.steps;
		if (values.sampler_name !== undefined) samplerName = values.sampler_name;
		if (values.scheduler !== undefined) scheduler = values.scheduler;
		if (values.random_seed !== undefined) randomSeed = values.random_seed;
		if (values.seed !== undefined) {
			seed = values.seed;
			randomSeed = false;
		}
		if (announce) {
			loadPresetModalOpen = false;
			presetSuccess = `'${preset.name}' 프리셋을 불러왔습니다. 저장된 항목만 적용했습니다.`;
		}
	}

	function loadPreset(preset: Preset) {
		applyPreset(preset, true);
	}

	function applyGenerationParameters(parameters: ImageGenerationParameters) {
		prompt = parameters.prompt;
		negativePrompt = parameters.negative_prompt;
		checkpoint = options.checkpoints.includes(parameters.checkpoint) ? parameters.checkpoint : options.default_checkpoint;
		loras = parameters.loras.filter(({ name }) => options.loras.includes(name)).map(({ name, strength }) => ({ name, strength }));
		cfg = parameters.cfg;
		steps = parameters.steps;
		samplerName = parameters.sampler_name;
		scheduler = parameters.scheduler;
		width = parameters.width;
		height = parameters.height;
		seed = parameters.seed;
		randomSeed = !parameters.seed.trim();
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
		if (fields.has('sampler_name') || fields.has('scheduler')) {
			fields.delete('sampler_name');
			fields.delete('scheduler');
			fields.add('sampling');
		}
		if (fields.has('seed') || fields.has('random_seed')) {
			fields.delete('random_seed');
			fields.add('seed');
		}
		const labels: Record<string, string> = Object.fromEntries(presetFieldOptions.map(({ key, label }) => [key, label]));
		return [...fields].map((field) => labels[field] ?? field).join(', ');
	}

	onMount(() => {
		void initialize();
		return () => {
			active = false;
		};
	});

	$effect(() => {
		const now = generationJobStore.now;
		const job = imageJobKey ? generationJobStore.jobs[imageJobKey] : undefined;
		if (!job) {
			elapsedSeconds = 0;
			return;
		}
		generationStatus = job.status;
		progress = job.progress;
		queuePosition = job.queuePosition;
		generationId = job.generationId;
		elapsedSeconds = generationJobStore.elapsedSeconds(job, now);
		imageUrl = job.imageUrl ?? '';
		const terminalKey = `${imageJobKey}:${job.status}`;
		if (job.status === 'completed' && announcedTerminal !== terminalKey) {
			successMessage = '이미지 생성이 완료되었습니다.';
			announcedTerminal = terminalKey;
		}
		if (job.status === 'failed' && announcedTerminal !== terminalKey) {
			generationError = job.error ?? '이미지 생성에 실패했습니다.';
			announcedTerminal = terminalKey;
		}
	});

	async function initialize() {
		resetResult();
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		await generationJobStore.initialize();
		const regenerationParameters = imageGenerationStore.consume();
		ready = true;
		try {
			[presets, options] = await Promise.all([
				apiJson<Preset[]>(`presets?type=${presetType}`),
				apiJson<ImageOptions>(`generation/image/options?family=${modelFamily}`)
			]);
			checkpoint = options.default_checkpoint;
			samplerName = options.default_sampler;
			scheduler = options.default_scheduler;
			if (regenerationParameters) {
				applyGenerationParameters(regenerationParameters);
			} else {
				const defaultPreset = presets.find((preset) => preset.is_default);
				if (defaultPreset) applyPreset(defaultPreset);
			}
		} catch (error) {
			optionsError = getErrorMessage(error);
		} finally {
			optionsLoading = false;
		}
	}

	async function generate() {
		imageJobKey = '';
		announcedTerminal = '';
		promptId = '';
		generationError = '';
		successMessage = '';
		imageUrl = '';
		generationId = '';
		progress = 0;
		queuePosition = null;
		if (!prompt.trim()) {
			generationError = '생성할 프롬프트를 입력해 주세요.';
			return;
		}
		if (promptEnhancementEnabled && !improvedPrompt.trim()) {
			generationError = '개선된 프롬프트를 먼저 생성해 주세요.';
			return;
		}

		if (!checkpoint) {
			generationError = '체크포인트를 선택해 주세요.';
			return;
		}
		if (!randomSeed && !seed.trim()) {
			generationError = '시드를 입력하거나 무작위 시드를 선택해 주세요.';
			return;
		}
		if (width % 8 !== 0 || height % 8 !== 0) {
			generationError = '이미지 가로·세로 크기는 8의 배수여야 합니다.';
			return;
		}

		generating = true;
		generationStatus = 'queued';
		try {
			const queued = await apiJson<{ prompt_id: string; client_id: string; generation_id: string; created_at: string; elapsed_seconds: number }>('generation/image', {
				method: 'POST',
				json: {
					model_family: modelFamily,
					prompt: prompt.trim(),
					prompt_enhancement_enabled: promptEnhancementEnabled,
					improved_prompt: promptEnhancementEnabled ? improvedPrompt.trim() : null,
					negative_prompt: negativePrompt.trim(),
					checkpoint,
					loras: loras.filter(({ name }) => name).map(({ name, strength }) => ({ name, strength })),
					cfg,
					steps,
					sampler_name: samplerName,
					scheduler,
					width,
					height,
					seed: randomSeed ? null : seed.trim() || null
				}
			});
			promptId = queued.prompt_id;
			generationId = queued.generation_id;
			imageJobKey = generationJobStore.track({
				kind: 'image',
				promptId: queued.prompt_id,
				clientId: queued.client_id,
				generationId: queued.generation_id,
				createdAt: Date.parse(queued.created_at),
				elapsedSeconds: queued.elapsed_seconds
			});
			await generationJobStore.waitForTerminal(imageJobKey);
		} catch (error) {
			if (!active) return;
			generationError = getErrorMessage(error);
			generationStatus = 'failed';
		} finally {
			generating = false;
		}
	}

	async function cancelGeneration() {
		if (!imageJobKey || !generating || cancelling) return;
		cancelling = true;
		generationError = '';
		try {
			await generationJobStore.cancel(imageJobKey);
		} catch (error) {
			generationError = getErrorMessage(error);
		} finally {
			cancelling = false;
		}
	}

	async function enhancePrompt() {
		promptEnhancementError = '';
		if (!prompt.trim()) {
			promptEnhancementError = '개선할 프롬프트를 입력해 주세요.';
			return;
		}
		enhancingPrompt = true;
		try {
			const result = await apiJson<{
				improved_prompt: { contents: string };
			}>('generation/image/enhance-prompt', {
				method: 'POST',
				timeout: 600_000,
				json: { prompt: prompt.trim() }
			});
			const resultPrompt = result.improved_prompt.contents.trim();
			if (!resultPrompt) throw new Error('개선된 프롬프트가 비어 있습니다.');
			improvedPrompt = resultPrompt;
		} catch (error) {
			promptEnhancementError = getErrorMessage(error);
		} finally {
			enhancingPrompt = false;
		}
	}

	function selectModelFamily(nextFamily: ModelFamilyTab) {
		if (nextFamily === modelFamily || nextFamily === 'krea2') return false;
		window.location.assign(`/generate/image?family=${nextFamily}`);
		return false;
	}

	function imageSourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function statusLabel(status: string) {
		return {
			queued: '대기 중',
			processing: '생성 중',
			completed: '완료',
			failed: '실패',
			cancelled: '취소됨'
		}[status] ?? status;
	}

	function resetResult() {
		generationError = '';
		successMessage = '';
		generationStatus = '';
		progress = 0;
		queuePosition = null;
		elapsedSeconds = 0;
		promptId = '';
		imageUrl = '';
		generationId = '';
		imageJobKey = '';
		announcedTerminal = '';
		generating = false;
		cancelling = false;
	}

	function getErrorMessage(error: unknown) {
		return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.';
	}

	function swapDimensions() {
		[width, height] = [height, width];
		aspectRatio = 'custom';
	}
</script>

<svelte:head>
	<title>{pageTitle} · Local Field</title>
	<meta name="description" content={`${familyLabel} 프롬프트를 사용한 텍스트 이미지 생성`} />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label={`${pageTitle} 페이지를 불러오는 중`} />
	</div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div class="space-y-4">
			<Typography as="h1" variant="display">{pageTitle}</Typography>
			<Tab items={modelFamilyTabs} value={modelFamily} ariaLabel="T2I 모델 family" onselect={selectModelFamily} />
		</div>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="result-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div>
							{#if generationStatus}
								<Typography as="p" variant="muted" class="mt-1">
									상태: {statusLabel(generationStatus)}
									{#if generationStatus === 'queued' || generationStatus === 'processing'} · {Math.round(progress)}%{/if}
									{#if generationStatus === 'queued' && queuePosition !== null} · 대기 {queuePosition}번째{/if}
									{#if generationStatus === 'queued' || generationStatus === 'processing'} · 경과 {formatElapsedSeconds(elapsedSeconds)}{:else} · 소요 {formatElapsedSeconds(elapsedSeconds)}{/if}
								</Typography>
							{/if}
						</div>
						<ImagePlus size={22} class="text-primary" strokeWidth={1.8} />
					</div>

					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if imageUrl}
							<ImageMedia source={imageUrl} sourceType={imageSourceType(imageUrl)} alt="생성 결과" class="min-h-[24rem] sm:min-h-[34rem]" />
						{:else if generating}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 sm:min-h-[34rem]">
								<LoadingSpinner size="lg" label="이미지 생성 중" />
								<p class="text-sm text-muted-foreground">이미지를 생성하고 있습니다.</p>
								<p class="text-2xl font-semibold tabular-nums text-primary">{formatElapsedSeconds(elapsedSeconds)}</p>
							</div>
						{:else}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-3 px-6 text-center sm:min-h-[34rem]">
								<div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
									<Sparkles size={26} strokeWidth={1.7} />
								</div>
								<p class="text-sm font-medium">아직 생성된 이미지가 없습니다.</p>
								<p class="max-w-sm text-xs leading-5 text-muted-foreground">프롬프트와 모델 설정을 입력한 뒤 이미지 생성 버튼을 눌러 주세요.</p>
							</div>
						{/if}
					</div>
					{#if generating && imageJobKey}
						<OutlinedButton class="mt-4 w-full" loading={cancelling} disabled={cancelling} onclick={() => void cancelGeneration()}>
							<X size={16} strokeWidth={1.9} />
							<span>{cancelling ? '이미지 생성 취소 중' : '이미지 생성 취소'}</span>
						</OutlinedButton>
					{/if}
					{#if imageUrl && generationId}
						<a href={`/vault/images/${generationId}`} class="mt-4 inline-flex text-sm font-semibold text-primary hover:underline">
							생성 상세 보기
						</a>
					{/if}
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="settings-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="settings-title"><Typography as="h2" variant="h2">파라미터 설정</Typography></div>
						</div>
						<div class="flex items-center gap-2">
							<IconOutlinedButton ariaLabel="프리셋 저장" title="프리셋 저장" loading={presetsLoading} disabled={optionsLoading || generating} onclick={() => void openSavePreset()}>
								<Save size={17} strokeWidth={1.8} />
							</IconOutlinedButton>
							<IconOutlinedButton ariaLabel="프리셋 불러오기" title="프리셋 불러오기" loading={presetsLoading} disabled={optionsLoading || generating} onclick={() => void openLoadPreset()}>
								<FolderOpen size={17} strokeWidth={1.8} />
							</IconOutlinedButton>
							{#if optionsLoading}<LoadingSpinner size="sm" label="모델 목록 불러오는 중" />{/if}
						</div>
					</div>

					<form class="mt-6 space-y-5 pb-24 sm:pb-0" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<div class="space-y-3">
							<div class="flex items-center justify-between gap-3">
								<label for="prompt" class="text-sm font-medium">긍정 프롬프트</label>
								<div class="flex items-center gap-2">
									{#if modelFamily === 'illustrious' && options.embeddings.length > 0}<OutlinedButton type="button" class="min-h-9 px-3 text-xs" disabled={generating} onclick={() => openEmbeddingPicker('positive')}>Embedding</OutlinedButton>{/if}
									<label for="prompt-enhancement-enabled" class="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg border border-border px-3 text-xs font-semibold text-muted-foreground transition hover:bg-muted">
										<input id="prompt-enhancement-enabled" type="checkbox" bind:checked={promptEnhancementEnabled} class="peer sr-only" />
										<span>프롬프트 개선</span>
										<span class="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground peer-checked:bg-primary/10 peer-checked:text-primary">{promptEnhancementEnabled ? 'ON' : 'OFF'}</span>
									</label>
									<OutlinedButton
										type="button"
										loading={enhancingPrompt}
										disabled={generating || !prompt.trim() || !promptEnhancementEnabled}
										class="min-h-9 px-3 text-xs"
										onclick={() => void enhancePrompt()}
									>
										<Sparkles size={14} strokeWidth={1.9} />
										<span>{enhancingPrompt ? '개선 중' : '프롬프트 개선'}</span>
									</OutlinedButton>
								</div>
							</div>
							<textarea id="prompt" bind:value={prompt} rows="5" required class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
							{#if promptEnhancementEnabled}
								<div class="space-y-3 rounded-xl border border-primary/20 bg-primary/5 p-3">
									<label class="block space-y-2" for="improved-prompt">
										<span class="text-sm font-medium">개선된 프롬프트</span>
										<textarea id="improved-prompt" bind:value={improvedPrompt} rows="5" disabled={enhancingPrompt} class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
									</label>

								</div>
							{/if}
						</div>

						<div class="space-y-2">
							<div class="flex items-center justify-between gap-3">
								<label for="negative-prompt" class="text-sm font-medium">부정 프롬프트</label>
								{#if modelFamily === 'illustrious' && options.embeddings.length > 0}<OutlinedButton type="button" class="min-h-9 px-3 text-xs" disabled={generating} onclick={() => openEmbeddingPicker('negative')}>Embedding</OutlinedButton>{/if}
							</div>
							<textarea id="negative-prompt" bind:value={negativePrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
						</div>

						<div class="space-y-2">
							<span class="text-sm font-medium">체크포인트</span>
							<button type="button" onclick={() => (checkpointModalOpen = true)} disabled={optionsLoading || options.checkpoints.length === 0} class="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-input bg-background px-3 py-2 text-left text-sm transition hover:bg-muted disabled:pointer-events-none disabled:opacity-50">
								<span class="min-w-0 truncate">{checkpoint || '체크포인트를 선택해 주세요'}</span>
								<span class="shrink-0 text-xs font-semibold text-primary">선택</span>
							</button>
						</div>
						<div class="space-y-3">
							<div class="flex items-center justify-between gap-3">
								<span class="text-sm font-medium">LoRA</span>
								<button type="button" onclick={() => (loraModalOpen = true)} disabled={optionsLoading || options.loras.length === 0} class="rounded-md px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">
									LoRA 선택
								</button>
							</div>
							{#if loras.length === 0}
								<p class="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">사용할 LoRA가 없습니다.</p>
							{:else}
								<div class="space-y-3">
									{#each loras as lora (lora.name)}
										<div class="rounded-lg border border-border p-3">
											<p class="break-all text-sm font-medium">{lora.name}</p>
											<label class="mt-3 block space-y-2" for={`lora-strength-${lora.name}`}>
												<span class="text-sm font-medium">Strength</span>
												<input id={`lora-strength-${lora.name}`} type="number" step="0.05" bind:value={lora.strength} class={numberInputClass} />
											</label>
										</div>
									{/each}
								</div>
							{/if}
						</div>

						<button type="button" onclick={() => (samplingModalOpen = true)} disabled={optionsLoading || !samplerName || !scheduler} class="flex min-h-11 w-full items-center justify-between gap-4 rounded-lg border border-input bg-background px-3 py-2 text-left transition hover:bg-muted disabled:pointer-events-none disabled:opacity-50">
							<span class="text-sm font-medium">샘플러 / 스케줄러</span>
							<span class="min-w-0 truncate text-xs text-muted-foreground">{samplerName} / {scheduler}</span>
						</button>

						<Select id="aspect-ratio" label="이미지 비율" options={aspectRatioOptions} bind:value={aspectRatio} />

						<div class="flex items-center justify-between gap-3">
							<span class="text-sm font-medium">이미지 크기</span>
							<IconOutlinedButton ariaLabel="가로와 세로 바꾸기" onclick={swapDimensions}>
								<ArrowLeftRight size={16} strokeWidth={1.9} />
							</IconOutlinedButton>
						</div>
						<div class="grid gap-4 sm:grid-cols-2">
							<label class="block space-y-2" for="width">
								<span class="text-sm font-medium">가로</span>
								<input id="width" type="number" min="64" max="2048" step="8" bind:value={width} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} />
							</label>
							<label class="block space-y-2" for="height">
								<span class="text-sm font-medium">세로</span>
								<input id="height" type="number" min="64" max="2048" step="8" bind:value={height} oninput={() => (aspectRatio = 'custom')} class={numberInputClass} />
							</label>
						</div>

						<div class="grid gap-4 sm:grid-cols-2">
							<label class="block space-y-2" for="cfg">
								<span class="text-sm font-medium">CFG</span>
								<input id="cfg" type="number" min="0" max="20" step="0.1" bind:value={cfg} class={numberInputClass} />
							</label>
							<label class="block space-y-2" for="steps">
								<span class="text-sm font-medium">Steps</span>
								<input id="steps" type="number" min="1" max="100" step="1" bind:value={steps} class={numberInputClass} />
							</label>
							</div>

							<div class="grid gap-4 sm:grid-cols-2">
							<label class="block space-y-2" for="seed">
								<span class="text-sm font-medium">Seed</span>
								<input id="seed" type="number" min="0" max="9223372036854775807" step="1" bind:value={seed} disabled={randomSeed} required={!randomSeed} class={numberInputClass} />
							</label>
							<label class="flex cursor-pointer items-center gap-3 self-end rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted sm:mb-0.5">
								<input id="random-seed" type="checkbox" bind:checked={randomSeed} class="size-4 accent-primary" />
								<span>무작위 시드</span>
							</label>
							</div>

							<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none">
							<PrimaryButton type="submit" loading={generating} disabled={optionsLoading || enhancingPrompt || !checkpoint} class="w-full">
								<Sparkles size={17} strokeWidth={1.9} />
								<span>{generating ? '생성 중' : '이미지 생성'}</span>
							</PrimaryButton>
						</div>
					</form>
				</section>
			</div>
		</div>
	</Layout>

	<Modal bind:open={checkpointModalOpen} title="체크포인트 선택" description="전체 또는 하위 folder에서 하나를 선택하세요.">
		<div class="space-y-3">
			<div class="flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="체크포인트 folder filter">
				<OutlinedButton class="min-h-9 px-3 text-xs" active={checkpointFolder === ''} onclick={() => (checkpointFolder = '')}>전체</OutlinedButton>
				{#if checkpointFolder}<OutlinedButton class="min-h-9 px-3 text-xs" onclick={() => (checkpointFolder = parentModelFolder(checkpointFolder))}>바로 위 폴더</OutlinedButton>{/if}
				{#each checkpointFolders as folder}
					<OutlinedButton class="min-h-9 px-3 text-xs" active={checkpointFolder === folder} onclick={() => (checkpointFolder = folder)}>{folder}</OutlinedButton>
				{/each}
			</div>
			<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
				{#each visibleCheckpoints as value}
					<button type="button" onclick={() => { checkpoint = value; checkpointModalOpen = false; }} aria-pressed={checkpoint === value} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${checkpoint === value ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}>
						<span>{value}</span>
						{#if checkpoint === value}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}
					</button>
				{/each}
			</div>
		</div>
	</Modal>

	<Modal bind:open={loraModalOpen} title="LoRA 선택" description="전체 또는 하위 folder에서 최대 8개를 선택하세요.">
		<div class="space-y-3">
			<div class="flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="LoRA folder filter">
				<OutlinedButton class="min-h-9 px-3 text-xs" active={loraFolder === ''} onclick={() => (loraFolder = '')}>전체</OutlinedButton>
				{#if loraFolder}<OutlinedButton class="min-h-9 px-3 text-xs" onclick={() => (loraFolder = parentModelFolder(loraFolder))}>바로 위 폴더</OutlinedButton>{/if}
				{#each loraFolders as folder}
					<OutlinedButton class="min-h-9 px-3 text-xs" active={loraFolder === folder} onclick={() => (loraFolder = folder)}>{folder}</OutlinedButton>
				{/each}
			</div>
			<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
				{#each visibleLoras as value}
					{@const selected = loras.some((lora) => lora.name === value)}
					<button type="button" onclick={() => toggleLora(value)} aria-pressed={selected} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${selected ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}>
						<span>{value}</span>
						{#if selected}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}
					</button>
				{/each}
			</div>
		</div>
		{#snippet footer()}<PrimaryButton onclick={() => (loraModalOpen = false)}>선택 완료</PrimaryButton>{/snippet}
	</Modal>

	<Modal bind:open={embeddingModalOpen} title={`${embeddingTarget === 'positive' ? '긍정' : '부정'} 프롬프트 Embedding`} description="전체 또는 하위 folder에서 Embedding token을 선택하세요.">
		<div class="space-y-3">
			<div class="flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="Embedding folder filter">
				<OutlinedButton class="min-h-9 px-3 text-xs" active={embeddingFolder === ''} onclick={() => (embeddingFolder = '')}>전체</OutlinedButton>
				{#if embeddingFolder}<OutlinedButton class="min-h-9 px-3 text-xs" onclick={() => (embeddingFolder = parentModelFolder(embeddingFolder))}>바로 위 폴더</OutlinedButton>{/if}
				{#each embeddingFolders as folder}
					<OutlinedButton class="min-h-9 px-3 text-xs" active={embeddingFolder === folder} onclick={() => (embeddingFolder = folder)}>{folder}</OutlinedButton>
				{/each}
			</div>
			<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
				{#each visibleEmbeddings as value}
					<button type="button" onclick={() => insertEmbedding(value)} class="min-h-14 break-all rounded-lg border border-border px-3 py-2 text-left text-xs transition hover:bg-muted">{value}</button>
				{/each}
			</div>
		</div>
	</Modal>

	<SamplingSelectionModal
		bind:open={samplingModalOpen}
		samplers={options.samplers}
		schedulers={options.schedulers}
		bind:samplerName
		bind:scheduler
	/>

	<Modal bind:open={savePresetModalOpen} title="프리셋 저장" closeOnBackdrop={!savingPreset}>
		<div class="space-y-5">
			<label class="block space-y-2" for="preset-name">
				<span class="text-sm font-medium">프리셋 이름</span>
				<input id="preset-name" bind:value={presetName} maxlength="100" class={numberInputClass} />
			</label>
			<div class="grid gap-2 sm:grid-cols-2">
				<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted">
					<input type="radio" name="preset-save-mode" value="new" checked={presetSaveMode === 'new'} onchange={() => (presetSaveMode = 'new')} class="size-4 accent-primary" />
					<span>새로 저장</span>
				</label>
				<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted">
					<input type="radio" name="preset-save-mode" value="overwrite" checked={presetSaveMode === 'overwrite'} onchange={() => (presetSaveMode = 'overwrite')} class="size-4 accent-primary" />
					<span>기존 프리셋 덮어쓰기</span>
				</label>
			</div>
			{#if presetSaveMode === 'overwrite'}
				<label class="block space-y-2" for="overwrite-preset">
					<span class="text-sm font-medium">덮어쓸 프리셋</span>
					<select id="overwrite-preset" bind:value={overwritePresetId} class={numberInputClass}>
						<option value="">프리셋을 선택해 주세요</option>
						{#each presets as preset (preset.id)}
							<option value={preset.id}>{preset.name} · {new Date(preset.updated_at).toLocaleString('ko-KR')}</option>
						{/each}
					</select>
				</label>
			{/if}
			<div class="space-y-3">
				<div class="flex items-center justify-between gap-3">
					<span class="text-sm font-medium">저장할 설정</span>
					<span class="text-xs text-muted-foreground">{selectedPresetFieldCount()}개 선택</span>
				</div>
				<div class="grid gap-2 sm:grid-cols-2">
					{#each presetFieldOptions as field}
						<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted">
							<input type="checkbox" checked={selectedPresetFields[field.key]} onchange={(event) => setPresetField(field.key, (event.currentTarget as HTMLInputElement).checked)} class="size-4 accent-primary" />
							<span>{field.label}</span>
						</label>
					{/each}
				</div>
			</div>
			{#if presetError}<p class="text-sm text-destructive" role="alert">{presetError}</p>{/if}
		</div>
		{#snippet footer()}
			<OutlinedButton disabled={savingPreset} onclick={() => (savePresetModalOpen = false)}>취소</OutlinedButton>
			<PrimaryButton loading={savingPreset} disabled={!presetName.trim() || selectedPresetFieldCount() === 0 || (presetSaveMode === 'overwrite' && !overwritePresetId)} onclick={() => void savePreset()}>저장</PrimaryButton>
		{/snippet}
	</Modal>

	<Modal bind:open={loadPresetModalOpen} title="프리셋 불러오기" closeOnBackdrop={!presetsLoading}>
		{#if presetsLoading}
			<div class="flex justify-center py-8"><LoadingSpinner size="md" label="프리셋 불러오는 중" /></div>
		{:else if presetError}
			<p class="py-4 text-sm text-destructive" role="alert">{presetError}</p>
		{:else if presets.length === 0}
			<p class="py-4 text-sm text-muted-foreground">저장된 프리셋이 없습니다.</p>
		{:else}
			<div class="space-y-2">
				{#each presets as preset (preset.id)}
					<div class="flex items-center justify-between gap-4 rounded-xl border border-border p-3">
						<div class="min-w-0">
							<p class="truncate text-sm font-semibold">{preset.name}</p>
							<p class="mt-1 truncate text-xs text-muted-foreground">{savedPresetLabels(preset)}</p>
						</div>
						<OutlinedButton class="shrink-0 px-3 text-xs" onclick={() => loadPreset(preset)}>불러오기</OutlinedButton>
					</div>
				{/each}
			</div>
		{/if}
	</Modal>

	{#if optionsError}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="모델 목록 불러오기 실패" message={optionsError} onclose={() => (optionsError = '')} />
		</div>
	{:else if promptEnhancementError}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="프롬프트 개선 실패" message={promptEnhancementError} onclose={() => (promptEnhancementError = '')} />
		</div>
	{:else if generationError}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="이미지 생성 실패" message={generationError} onclose={() => (generationError = '')} />
		</div>
	{:else if successMessage}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="positive" title="생성 완료" message={successMessage} onclose={() => (successMessage = '')} />
		</div>
	{:else if presetSuccess}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="positive" title="프리셋" message={presetSuccess} onclose={() => (presetSuccess = '')} />
		</div>
	{/if}
{/if}
