<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { ArrowLeftRight, Check, ChevronLeft, ChevronRight, FolderOpen, HardDrive, ImagePlus, Save, Sparkles, X } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import Modal from '../../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import SearchBar from '../../../../components/inputs/searchbar.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import SamplingSelectionModal from '../../../../components/presets/sampling-selection-modal.svelte';
	import ImagePresetModal from '../../../../components/presets/image-preset-modal.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { imageGenerationStore, type ImageGenerationParameters } from '$lib/stores/image-generation.svelte';
	import { apiBlob, apiForm, apiJson } from '$lib/utils/api';
	import { formatElapsedSeconds, formatFileSize } from '$lib/utils/generation';
	import { filterModelFolder, modelFolders, parentModelFolder } from '$lib/utils/model-folders';
	import { imageGenerationModeTabs, imageModelFamilyTabs, imagePresetCategories, type ImageGenerationMode, type ImageModelFamily, type ImagePresetType, type Preset, type PresetValues } from '$lib/types/presets';

	type ImageFamily = 'anima' | 'illustrious';
	type ImageFamilyTab = ImageFamily | 'krea2';
	type ImageDimensions = { width: number; height: number };
	type ImageOptions = {
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
	type AcceptedImageGeneration = {
		prompt_id: string;
		client_id: string;
		generation_id: string;
		status: 'queued' | 'processing';
		progress?: number;
		queue_position?: number | null;
		created_at: string;
		elapsed_seconds: number;
	};
	type StoredImageAsset = {
		file_id: string;
		filename: string;
		content_type: string;
		media_kind: 'image';
		source_type: string;
		created_at: string;
		size: number;
		url: string | null;
	};
	type StoredImagePage = {
		items: StoredImageAsset[];
		page: number;
		total_pages: number;
	};
	type SelectionSource = 'device' | 'stored';
	type StoredSort = 'latest' | 'oldest' | 'name';
	type StoredSource = 'uploaded' | 'generated';

	const emptyOptions: ImageOptions = {
		checkpoints: [],
		loras: [],
		embeddings: [],
		samplers: [],
		schedulers: [],
		default_checkpoint: '',
		default_sampler: '',
		default_scheduler: ''
	};
	const numberInputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50';
	const fileInputClass = 'block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary disabled:cursor-not-allowed disabled:opacity-50';
	const maxSeed = BigInt('9223372036854775807');
	const maxImageDimension = 2048;
	const minImageDimension = 64;
	const imageDimensionStep = 8;
const selectionSourceTabs: { value: SelectionSource; label: string }[] = [
	{ value: 'device', label: '기기 저장소' },
	{ value: 'stored', label: '저장된 콘텐츠' }
];
const storedSourceTabs: { value: StoredSource; label: string }[] = [
	{ value: 'uploaded', label: '업로드' },
	{ value: 'generated', label: '생성' }
];
// ponytail: Krea2 R2I stays disabled until its dedicated style-reference LoRA is installed; add that workflow instead of routing it through generic VAE I2I.
const modelFamilyTabs: { value: ImageFamilyTab; label: string; disabled?: boolean }[] = [
	{ value: 'anima', label: 'ANIMA' },
	{ value: 'illustrious', label: 'ILLUSTRIOUS' },
	{ value: 'krea2', label: 'KREA2', disabled: true }
];

	let family = $derived<ImageFamily>(page.url.searchParams.get('family') === 'illustrious' ? 'illustrious' : 'anima');
	let familyLabel = $derived(family === 'illustrious' ? 'Illustrious' : 'Anima');
	let routeTitle = $derived('I2I');
	let presetType = $derived<ImagePresetType>(family === 'illustrious' ? 'i2i_illustrious' : 'i2i_anima');
	let storedImagePresetType = $state<ImagePresetType>('t2i_anima');
	let storedImagePreset = $derived(imagePresetCategories.find((category) => category.value === storedImagePresetType) ?? imagePresetCategories[0]);

	let active = true;
	let ready = $state(false);
	let optionsLoading = $state(true);
	let optionsError = $state('');
	let sourceError = $state('');
	let generationError = $state('');
	let successMessage = $state('');
	let infoMessage = $state('');
	let generating = $state(false);
	let uploading = $state(false);
	let cancelling = $state(false);
	let generationStatus = $state('');
	let progress = $state(0);
	let queuePosition = $state<number | null>(null);
	let elapsedSeconds = $state(0);
	let imageUrl = $state('');
	let generationId = $state('');
	let imageJobKey = $state('');
	let announcedTerminal = $state('');
	let options = $state<ImageOptions>({ ...emptyOptions });
	let presets = $state<Preset[]>([]);
	let presetsLoading = $state(false);
	let presetOpen = $state(false);
	let presetLoadOpen = $state(false);
	let presetError = $state('');
	let presetSuccess = $state('');
	let positivePromptPrefix = $state('');
	let prompt = $state('');
	let negativePromptPrefix = $state('');
	let negativePrompt = $state('');
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
	let width = $state(1024);
	let height = $state(1024);
	let denoise = $state(0.65);
	let sourceFile = $state<File | null>(null);
	let sourceFileId = $state('');
	let sourceImageUrl = $state('');
	let sourceInput = $state<HTMLInputElement>();
	let sourceSelectionOpen = $state(false);
	let selectionSource = $state<SelectionSource>('device');
	let storedAssetSource = $state<StoredSource>('uploaded');
	let storedAssets = $state<StoredImageAsset[]>([]);
	let storedLoading = $state(false);
	let storedSearch = $state('');
	let storedSort = $state<StoredSort>('latest');
	let storedPage = $state(1);
	let storedTotalPages = $state(0);
	let storedRequestId = 0;
	let sourceStoredAsset = $state<StoredImageAsset | null>(null);
	let sourceDimensions = $state<ImageDimensions | null>(null);
	let sourceMetadataLoading = $state(false);
	let sizeApplying = $state(false);

	let optionsRequestId = 0;
	let sourceMetadataRequestId = 0;
	let regenerationParameters: ImageGenerationParameters | null = null;

	onMount(() => {
		resetRouteJobState();
		void initialize();
		return () => {
			active = false;
			optionsRequestId += 1;
			sourceMetadataRequestId += 1;
		};
	});

	$effect(() => {
		const currentFamily = family;
		if (!ready) return;
		void loadOptions(currentFamily);
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
			successMessage = `${familyLabel} 이미지 변환이 완료되었습니다.`;
			announcedTerminal = terminalKey;
		}
		if (job.status === 'failed' && announcedTerminal !== terminalKey) {
			generationError = job.error ?? '이미지 변환에 실패했습니다.';
			announcedTerminal = terminalKey;
		}
	});

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		await generationJobStore.initialize();
		regenerationParameters = imageGenerationStore.consume();
		ready = true;
	}

	async function loadOptions(targetFamily: ImageFamily) {
		const requestId = ++optionsRequestId;
		const targetPresetType: ImagePresetType = targetFamily === 'illustrious' ? 'i2i_illustrious' : 'i2i_anima';
		optionsLoading = true;
		optionsError = '';
		checkpointModalOpen = false;
		loraModalOpen = false;
		checkpointFolder = '';
		loraFolder = '';
		embeddingFolder = '';
		samplingModalOpen = false;
		options = { ...emptyOptions };
		checkpoint = '';
		loras = [];
		samplerName = '';
		scheduler = '';
		try {
			const [loaded, loadedPresets] = await Promise.all([
				apiJson<ImageOptions>(`generation/image/options?family=${targetFamily}`),
				apiJson<Preset[]>(`presets?type=${targetPresetType}`)
			]);
			if (!active || requestId !== optionsRequestId || family !== targetFamily) return;
			options = loaded;
			presets = loadedPresets;
			checkpoint = loaded.default_checkpoint;
			samplerName = loaded.default_sampler;
			scheduler = loaded.default_scheduler;
			if (regenerationParameters) {
				applyGenerationParameters(regenerationParameters);
				regenerationParameters = null;
			} else {
				const defaultPreset = loadedPresets.find((preset) => preset.is_default);
				if (defaultPreset) applyPreset(defaultPreset);
			}
		} catch (error) {
			if (active && requestId === optionsRequestId) optionsError = getErrorMessage(error);
		} finally {
			if (active && requestId === optionsRequestId) optionsLoading = false;
		}
	}

	function applyGenerationParameters(parameters: ImageGenerationParameters) {
		if (parameters.generation_mode !== 'i2i' || (parameters.model_family && parameters.model_family !== family)) return;
		positivePromptPrefix = parameters.positive_prompt_prefix ?? '';
		prompt = parameters.prompt;
		negativePromptPrefix = parameters.negative_prompt_prefix ?? '';
		negativePrompt = parameters.negative_prompt;
		checkpoint = options.checkpoints.includes(parameters.checkpoint) ? parameters.checkpoint : options.default_checkpoint;
		loras = parameters.loras.filter(({ name }) => options.loras.includes(name)).map(({ name, strength }) => ({ name, strength }));
		cfg = parameters.cfg;
		steps = parameters.steps;
		samplerName = options.samplers.includes(parameters.sampler_name) ? parameters.sampler_name : options.default_sampler;
		scheduler = options.schedulers.includes(parameters.scheduler) ? parameters.scheduler : options.default_scheduler;
		width = parameters.width;
		height = parameters.height;
		seed = parameters.seed;
		randomSeed = !parameters.seed.trim();
		denoise = parameters.denoise ?? 0.65;
		sourceFileId = parameters.source_file_id ?? '';
		sourceImageUrl = parameters.source_image_url ?? '';
		sourceStoredAsset = null;
		sourceDimensions = null;
		if (sourceImageUrl && sourceFileId) void inspectSourceImage(sourceImageUrl, sourceFileId);
	}

	function imagePresetInitialValues(): PresetValues {
		return {
			positive_prompt_prefix: positivePromptPrefix.trim(),
			prompt: prompt.trim(),
			negative_prompt_prefix: negativePromptPrefix.trim(),
			negative_prompt: negativePrompt.trim(),
			checkpoint,
			loras: loras.map(({ name, strength }) => ({ name, strength })),
			aspect_ratio: 'custom',
			width: Number(width),
			height: Number(height),
			denoise: Number(denoise),
			cfg: Number(cfg),
			steps: Number(steps),
			sampler_name: samplerName,
			scheduler,
			random_seed: randomSeed,
			...(randomSeed || !seed.trim() ? {} : { seed: seed.trim() })
		};
	}

	function openImagePresetSave() {
		presetError = '';
		presetOpen = true;
	}

	async function openImagePresetLoad() {
		presetLoadOpen = true;
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

	function applyPreset(preset: Preset, announce = false) {
		const values = preset.values;
		if (values.positive_prompt_prefix !== undefined) positivePromptPrefix = values.positive_prompt_prefix;
		if (values.prompt !== undefined) prompt = values.prompt;
		if (values.negative_prompt_prefix !== undefined) negativePromptPrefix = values.negative_prompt_prefix;
		if (values.negative_prompt !== undefined) negativePrompt = values.negative_prompt;
		if (values.checkpoint !== undefined && options.checkpoints.includes(values.checkpoint)) checkpoint = values.checkpoint;
		if (values.loras !== undefined) loras = values.loras.filter(({ name }) => options.loras.includes(name)).map(({ name, strength }) => ({ name, strength }));
		if (values.width !== undefined) width = values.width;
		if (values.height !== undefined) height = values.height;
		if (values.denoise !== undefined) denoise = values.denoise;
		if (values.cfg !== undefined) cfg = values.cfg;
		if (values.steps !== undefined) steps = values.steps;
		if (values.sampler_name !== undefined && options.samplers.includes(values.sampler_name)) samplerName = values.sampler_name;
		if (values.scheduler !== undefined && options.schedulers.includes(values.scheduler)) scheduler = values.scheduler;
		if (values.random_seed !== undefined) randomSeed = values.random_seed;
		if (values.seed !== undefined) {
			seed = values.seed;
			randomSeed = false;
		}
		if (announce) {
			presetLoadOpen = false;
			presetSuccess = `'${preset.name}' 프리셋을 불러왔습니다. 저장된 항목만 적용했습니다.`;
		}
	}

	function handlePresetSaved(saved: Preset) {
		presets = [saved, ...presets.filter((preset) => preset.id !== saved.id)];
		presetSuccess = `'${saved.name}' 프리셋을 저장했습니다.`;
	}

	function selectModelFamily(nextFamily: ImageFamilyTab) {
		if (nextFamily === family || nextFamily === 'krea2') return false;
		window.location.assign(`/generate/image-to-image?family=${nextFamily}`);
		return false;
	}

	function openSourceSelection() {
		if (generating) return;
		selectionSource = 'stored';
		storedAssetSource = 'generated';
		storedImagePresetType = 't2i_anima';
		storedAssets = [];
		storedSearch = '';
		storedSort = 'latest';
		storedPage = 1;
		storedTotalPages = 0;
		sourceSelectionOpen = true;
		void loadStoredImages(1);
	}

	function selectSelectionSource(source: SelectionSource) {
		selectionSource = source;
		if (source === 'stored') void loadStoredImages(1);
	}

	function selectStoredAssetSource(source: StoredSource) {
		if (storedAssetSource === source) return;
		storedAssetSource = source;
		void loadStoredImages(1);
	}

	function selectStoredImagePresetType(type: ImagePresetType) {
		if (storedImagePresetType === type) return;
		storedImagePresetType = type;
		void loadStoredImages(1);
	}

	function selectStoredImageFamily(family: ImageModelFamily) {
		const type = imagePresetCategories.find(
			(category) => category.modelFamily === family && category.generationMode === storedImagePreset.generationMode
		)?.value;
		if (type) selectStoredImagePresetType(type);
	}

	function selectStoredImageMode(mode: ImageGenerationMode) {
		const type = imagePresetCategories.find(
			(category) => category.modelFamily === storedImagePreset.modelFamily && category.generationMode === mode
		)?.value;
		if (type) selectStoredImagePresetType(type);
	}

	async function loadStoredImages(requestedPage = storedPage) {
		const requestId = ++storedRequestId;
		storedLoading = true;
		try {
			const params = new URLSearchParams({
				include_generated: 'true',
				media_kind: 'image',
				source: storedAssetSource,
				search: storedSearch,
				sort: storedSort,
				page: String(requestedPage)
			});
			if (storedAssetSource === 'generated') {
				params.set('generation_mode', storedImagePreset.generationMode);
				params.set('model_family', storedImagePreset.modelFamily);
			}
			const result = await apiJson<StoredImagePage>(`uploads?${params.toString()}`);
			if (active && requestId === storedRequestId) {
				storedAssets = result.items;
				storedPage = result.page;
				storedTotalPages = result.total_pages;
			}
		} catch (error) {
			if (active && requestId === storedRequestId) sourceError = getErrorMessage(error);
		} finally {
			if (active && requestId === storedRequestId) storedLoading = false;
		}
	}

	function changeStoredFilter() {
		void loadStoredImages(1);
	}

	function changeStoredPage(nextPage: number) {
		if (nextPage < 1 || nextPage > storedTotalPages) return;
		void loadStoredImages(nextPage);
	}

	function selectStoredImage(asset: StoredImageAsset) {
		sourceMetadataRequestId += 1;
		sourceError = '';
		sourceFile = null;
		sourceFileId = asset.file_id;
		sourceImageUrl = asset.url ?? '';
		sourceStoredAsset = asset;
		sourceDimensions = null;
		sourceMetadataLoading = false;
		if (sourceInput) sourceInput.value = '';
		sourceSelectionOpen = false;
		if (asset.url) void inspectSourceImage(asset.url, asset.file_id);
	}

	function handleSourceFile(event: Event) {
		if (!(event.currentTarget instanceof HTMLInputElement) || generating) return;
		const files = event.currentTarget.files;
		if (!files || files.length === 0) return;
		if (files.length !== 1) {
			sourceError = '소스 이미지는 정확히 한 장만 선택해 주세요.';
			return;
		}
		const file = files[0];
		if (!file.type.startsWith('image/')) {
			sourceError = '이미지 파일만 선택할 수 있습니다.';
			return;
		}
		if (file.size <= 0) {
			sourceError = '비어 있는 이미지 파일은 사용할 수 없습니다.';
			return;
		}
		sourceError = '';
		sourceFile = file;
		sourceFileId = '';
		sourceImageUrl = '';
		sourceStoredAsset = null;
		sourceDimensions = null;
		event.currentTarget.value = '';
		sourceSelectionOpen = false;
		void inspectSourceImage(file);
	}

	async function inspectSourceImage(source: File | string, expectedFileId = '') {
		const requestId = ++sourceMetadataRequestId;
		sourceMetadataLoading = true;
		try {
			const dimensions = await readImageDimensions(source);
			const currentSource = source instanceof File
				? sourceFile === source
				: sourceFileId === expectedFileId && sourceImageUrl === source;
			if (!active || requestId !== sourceMetadataRequestId || !currentSource) return;
			sourceDimensions = dimensions;
		} catch {
			if (active && requestId === sourceMetadataRequestId) {
				sourceDimensions = null;
				sourceError = '선택한 이미지의 원본 크기를 읽지 못했습니다. 다른 이미지를 선택해 주세요.';
			}
		} finally {
			if (active && requestId === sourceMetadataRequestId) sourceMetadataLoading = false;
		}
	}

	async function readImageDimensions(source: Blob | string) {
		let objectUrl = '';
		try {
			if (source instanceof Blob) objectUrl = URL.createObjectURL(source);
			else if (!/^(https?:)?\/\//.test(source)) objectUrl = URL.createObjectURL(await apiBlob(source));
			const url = objectUrl || (typeof source === 'string' ? source : '');
			return await new Promise<ImageDimensions>((resolve, reject) => {
				const image = new Image();
				image.onload = () => image.naturalWidth > 0 && image.naturalHeight > 0
					? resolve({ width: image.naturalWidth, height: image.naturalHeight })
					: reject(new Error('invalid image dimensions'));
				image.onerror = () => reject(new Error('image metadata unavailable'));
				image.src = url;
			});
		} finally {
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		}
	}

	function normalizedImageDimensions(dimensions: ImageDimensions) {
		const scale = Math.min(1, maxImageDimension / dimensions.width, maxImageDimension / dimensions.height);
		const normalize = (value: number) => {
			const stepped = Math.round((value * scale) / imageDimensionStep) * imageDimensionStep;
			return Math.max(minImageDimension, Math.min(maxImageDimension, stepped));
		};
		return { width: normalize(dimensions.width), height: normalize(dimensions.height) };
	}

	async function applySourceSize() {
		const selectedFile = sourceFile;
		const selectedFileId = sourceFileId;
		const selectedUrl = sourceImageUrl;
		const source = selectedFile ?? selectedUrl;
		if (!source || sizeApplying || generating) return;
		sizeApplying = true;
		sourceError = '';
		try {
			const dimensions = sourceDimensions ?? (await readImageDimensions(source));
			if (sourceFile !== selectedFile || sourceFileId !== selectedFileId || sourceImageUrl !== selectedUrl) return;
			sourceDimensions = dimensions;
			const normalized = normalizedImageDimensions(dimensions);
			width = normalized.width;
			height = normalized.height;
		} catch {
			sourceError = '선택한 이미지의 크기를 적용하지 못했습니다.';
		} finally {
			sizeApplying = false;
		}
	}

	function clearSource() {
		sourceMetadataRequestId += 1;
		sourceFile = null;
		sourceFileId = '';
		sourceImageUrl = '';
		sourceStoredAsset = null;
		sourceDimensions = null;
		sourceMetadataLoading = false;
		sizeApplying = false;
		if (sourceInput) sourceInput.value = '';
	}

	function toggleLora(name: string) {
		if (generating) return;
		const selected = loras.some((lora) => lora.name === name);
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

	function validateInputs() {
		if (optionsLoading) return '모델 목록을 불러오는 중입니다.';
		if (optionsError) return '모델 목록을 다시 불러온 뒤 시도해 주세요.';
		if (!sourceFile && !sourceFileId) return '변환할 소스 이미지를 선택해 주세요.';
		if (sourceFile && (!sourceFile.type.startsWith('image/') || sourceFile.size <= 0)) return '유효한 이미지 파일을 선택해 주세요.';
		if (sourceFile && sourceMetadataLoading) return '소스 이미지 정보를 확인하는 중입니다.';
		if (sourceFile && !sourceDimensions) return '원본 크기를 확인할 수 있는 이미지를 선택해 주세요.';
		if (!prompt.trim()) return '생성할 프롬프트를 입력해 주세요.';
		if (positivePromptPrefix.trim().length > 5000) return '긍정 프롬프트 Prefix는 5,000자 이하로 입력해 주세요.';
		if (prompt.trim().length > 5000) return '긍정 프롬프트는 5,000자 이하로 입력해 주세요.';
		if (negativePromptPrefix.trim().length > 5000) return '부정 프롬프트 Prefix는 5,000자 이하로 입력해 주세요.';
		if (negativePrompt.trim().length > 5000) return '부정 프롬프트는 5,000자 이하로 입력해 주세요.';
		if (!checkpoint || !options.checkpoints.includes(checkpoint)) return '체크포인트를 선택해 주세요.';
		if (new Set(loras.map(({ name }) => name)).size !== loras.length) return 'LoRA 선택을 확인해 주세요.';
		if (loras.some(({ name, strength }) => !name.trim() || !options.loras.includes(name) || !Number.isFinite(Number(strength)))) return 'LoRA와 Strength 값을 확인해 주세요.';
		if (!isValidDimension(width) || !isValidDimension(height)) return '이미지 가로·세로는 64~2048 범위의 8의 배수여야 합니다.';
		if (!Number.isFinite(Number(denoise)) || Number(denoise) < 0 || Number(denoise) > 1) return 'Denoise는 0.0에서 1.0 사이로 입력해 주세요.';
		if (!Number.isFinite(Number(cfg)) || Number(cfg) < 0 || Number(cfg) > 20) return 'CFG는 0에서 20 사이로 입력해 주세요.';
		if (!Number.isInteger(Number(steps)) || Number(steps) < 1 || Number(steps) > 100) return 'Steps는 1에서 100 사이의 정수로 입력해 주세요.';
		if (!samplerName || !options.samplers.includes(samplerName)) return '샘플러를 선택해 주세요.';
		if (!scheduler || !options.schedulers.includes(scheduler)) return '스케줄러를 선택해 주세요.';
		if (!randomSeed && !isValidSeed(seed)) return 'Seed는 0부터 9223372036854775807 사이의 정수 문자열로 입력해 주세요.';
		return '';
	}

	function isValidDimension(value: number) {
		const parsed = Number(value);
		return Number.isInteger(parsed) && parsed >= minImageDimension && parsed <= maxImageDimension && parsed % imageDimensionStep === 0;
	}

	function isValidSeed(value: string) {
		const normalized = value.trim();
		if (!/^\d+$/.test(normalized)) return false;
		try {
			return BigInt(normalized) <= maxSeed;
		} catch {
			return false;
		}
	}

	async function generate() {
		if (generating) return;
		resetRouteJobState();
		const validationError = validateInputs();
		if (validationError) {
			generationError = validationError;
			return;
		}
		if (!sourceFile && !sourceFileId) return;

		const requestFamily = family;
		const form = new FormData();
		form.append('payload', JSON.stringify({
			model_family: requestFamily,
			source: sourceFile ? { file_index: 0 } : { file_id: sourceFileId },
			positive_prompt_prefix: positivePromptPrefix.trim(),
			prompt: prompt.trim(),
			negative_prompt_prefix: negativePromptPrefix.trim(),
			negative_prompt: negativePrompt.trim(),
			checkpoint,
			loras: loras.map(({ name, strength }) => ({ name, strength: Number(strength) })),
			cfg: Number(cfg),
			steps: Number(steps),
			sampler_name: samplerName,
			scheduler,
			width: Number(width),
			height: Number(height),
			seed: randomSeed ? null : seed.trim(),
			denoise: Number(denoise)
		}));
		if (sourceFile) form.append('files', sourceFile, sourceFile.name);

		generating = true;
		uploading = true;
		generationStatus = 'queued';
		try {
			const accepted = await apiForm<AcceptedImageGeneration>('generation/image/i2i', form, { timeout: 120_000 });
			if (!active) return;
			uploading = false;
			generationId = accepted.generation_id;
			imageJobKey = generationJobStore.track({
				kind: 'image',
				promptId: accepted.prompt_id,
				clientId: accepted.client_id,
				generationId: accepted.generation_id,
				status: accepted.status,
				progress: accepted.progress ?? 0,
				queuePosition: accepted.queue_position ?? null,
				createdAt: Date.parse(accepted.created_at) || Date.now(),
				elapsedSeconds: accepted.elapsed_seconds
			});
			await generationJobStore.waitForTerminal(imageJobKey);
		} catch (error) {
			if (!active) return;
			generationError = getErrorMessage(error);
			generationStatus = 'failed';
		} finally {
			uploading = false;
			generating = false;
		}
	}

	async function cancelGeneration() {
		if (!imageJobKey || !generating || uploading || cancelling) return;
		cancelling = true;
		generationError = '';
		try {
			await generationJobStore.cancel(imageJobKey);
			infoMessage = '이미지 변환을 취소했습니다.';
		} catch (error) {
			generationError = getErrorMessage(error);
		} finally {
			cancelling = false;
		}
	}

	function imageSourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function storedSourceLabel(asset: StoredImageAsset) {
		return asset.source_type === 'image_generation' ? '생성 이미지' : '업로드 콘텐츠';
	}

	function statusLabel(status: string) {
		return {
			queued: uploading ? '소스 이미지 업로드 중' : '대기 중',
			processing: '변환 중',
			completed: '완료',
			failed: '실패',
			cancelled: '취소됨'
		}[status] ?? status;
	}

	function resetRouteJobState() {
		generationError = '';
		successMessage = '';
		infoMessage = '';
		generationStatus = '';
		progress = 0;
		queuePosition = null;
		elapsedSeconds = 0;
		imageUrl = '';
		generationId = '';
		imageJobKey = '';
		announcedTerminal = '';
		generating = false;
		uploading = false;
		cancelling = false;
	}

	function getErrorMessage(error: unknown) {
		return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.';
	}

	function swapDimensions() {
		[width, height] = [height, width];
	}
</script>

<svelte:head>
	<title>{routeTitle} · Local Field</title>
	<meta name="description" content={`${familyLabel} 모델과 한 장의 로컬 소스 이미지를 사용한 이미지 변환`} />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="이미지 변환 페이지를 불러오는 중" />
	</div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div class="space-y-4">
				<Typography as="h1" variant="display">{routeTitle}</Typography>
				<Tab items={modelFamilyTabs} value={family} ariaLabel="I2I 모델 family" onselect={selectModelFamily} />
			</div>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="i2i-result-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="i2i-result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div>
							{#if generationStatus}
								<Typography as="p" variant="muted" class="mt-1">
									상태: {statusLabel(generationStatus)}
									{#if (generationStatus === 'queued' || generationStatus === 'processing') && !uploading} · {Math.round(progress)}%{/if}
									{#if generationStatus === 'queued' && queuePosition !== null && !uploading} · 대기 {queuePosition}번째{/if}
									{#if generationStatus === 'queued' || generationStatus === 'processing'} · 경과 {formatElapsedSeconds(elapsedSeconds)}{:else} · 소요 {formatElapsedSeconds(elapsedSeconds)}{/if}
								</Typography>
							{/if}
						</div>
						<ImagePlus size={22} class="text-primary" strokeWidth={1.8} />
					</div>

					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if imageUrl}
							<ImageMedia source={imageUrl} sourceType={imageSourceType(imageUrl)} alt={`${familyLabel} 이미지 변환 결과`} class="min-h-[24rem] sm:min-h-[34rem]" />
						{:else if generating}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 px-6 text-center sm:min-h-[34rem]">
								<LoadingSpinner size="lg" label={uploading ? '소스 이미지 업로드 중' : '이미지 변환 중'} />
								<p class="text-sm text-muted-foreground">{uploading ? '선택한 소스 이미지를 전송하고 있습니다.' : `${familyLabel} 이미지로 변환하고 있습니다.`}</p>
								<p class="text-2xl font-semibold tabular-nums text-primary">{formatElapsedSeconds(elapsedSeconds)}</p>
							</div>
						{:else}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-3 px-6 text-center sm:min-h-[34rem]">
								<div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Sparkles size={26} strokeWidth={1.7} /></div>
								<p class="text-sm font-medium">아직 변환된 이미지가 없습니다.</p>
								<p class="max-w-sm text-xs leading-5 text-muted-foreground">소스 이미지와 생성 설정을 확인한 뒤 이미지 변환 버튼을 눌러 주세요.</p>
							</div>
						{/if}
					</div>
					{#if generating && imageJobKey}
						<OutlinedButton class="mt-4 w-full" loading={cancelling} disabled={uploading || cancelling} onclick={() => void cancelGeneration()}>
							<X size={16} strokeWidth={1.9} />
							<span>{cancelling ? '이미지 변환 취소 중' : '이미지 변환 취소'}</span>
						</OutlinedButton>
					{/if}
					{#if imageUrl && generationId}
						<a href={`/vault/images/${generationId}`} class="mt-4 inline-flex text-sm font-semibold text-primary hover:underline">생성 상세 보기</a>
					{/if}
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="i2i-settings-title">
					<div class="flex items-center justify-between gap-4">
						<div id="i2i-settings-title"><Typography as="h2" variant="h2">변환 설정</Typography></div>
						<div class="flex items-center gap-2">
							<IconOutlinedButton ariaLabel="I2I 프리셋 저장" title="프리셋 저장" disabled={generating || optionsLoading} onclick={openImagePresetSave}><Save size={17} strokeWidth={1.8} /></IconOutlinedButton>
							<IconOutlinedButton ariaLabel="I2I 프리셋 불러오기" title="프리셋 불러오기" loading={presetsLoading} disabled={generating} onclick={() => void openImagePresetLoad()}><FolderOpen size={17} strokeWidth={1.8} /></IconOutlinedButton>
							{#if optionsLoading}<LoadingSpinner size="sm" label="모델 목록 불러오는 중" />{/if}
						</div>
					</div>

					<form class="mt-6 space-y-5 pb-24 sm:pb-0" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<div class="space-y-3">
							<span class="text-sm font-medium">소스 이미지</span>
							<OutlinedButton type="button" class="w-full" disabled={generating} onclick={openSourceSelection}><HardDrive size={16} />소스 이미지 선택</OutlinedButton>
							{#if sourceFile}
								<div class="overflow-hidden rounded-xl border border-border bg-muted/30">
									<div class="relative">
										<IconOutlinedButton variant="filled" ariaLabel="소스 이미지 선택 해제" title="소스 이미지 선택 해제" class="absolute right-2 top-2 z-10 bg-card/90" disabled={generating} onclick={() => clearSource()}>
											<X size={16} strokeWidth={2} />
										</IconOutlinedButton>
										<ImageMedia source={sourceFile} sourceType="local" alt="선택한 이미지 변환 소스" class="max-h-80" />
									</div>
									<dl class="grid gap-2 border-t border-border px-3 py-3 text-xs sm:grid-cols-2">
										<div class="min-w-0"><dt class="text-muted-foreground">파일 이름</dt><dd class="mt-1 truncate font-medium" title={sourceFile.name}>{sourceFile.name}</dd></div>
										<div><dt class="text-muted-foreground">파일 형식</dt><dd class="mt-1 font-medium">{sourceFile.type || '알 수 없음'}</dd></div>
										<div><dt class="text-muted-foreground">파일 크기</dt><dd class="mt-1 font-medium">{formatFileSize(sourceFile.size)}</dd></div>
										<div><dt class="text-muted-foreground">원본 크기</dt><dd class="mt-1 font-medium" aria-live="polite">{sourceMetadataLoading ? '확인 중' : sourceDimensions ? `${sourceDimensions.width} × ${sourceDimensions.height}` : '확인 실패'}</dd></div>
									</dl>
									<OutlinedButton type="button" class="w-full rounded-none border-0 border-t" loading={sizeApplying} disabled={generating || sourceMetadataLoading || !sourceDimensions} onclick={() => void applySourceSize()}>이 사이즈 사용</OutlinedButton>
								</div>
							{:else if sourceFileId}
								<div class="overflow-hidden rounded-xl border border-border bg-muted/30">
									<div class="relative">
										<IconOutlinedButton variant="filled" ariaLabel="소스 이미지 선택 해제" title="소스 이미지 선택 해제" class="absolute right-2 top-2 z-10 bg-card/90" disabled={generating} onclick={clearSource}><X size={16} strokeWidth={2} /></IconOutlinedButton>
										{#if sourceImageUrl}
											<ImageMedia source={sourceImageUrl} sourceType={imageSourceType(sourceImageUrl)} alt="선택한 보관함 이미지 변환 소스" class="max-h-80" />
										{:else}
											<div class="flex min-h-48 flex-col items-center justify-center gap-2 px-4 text-center text-muted-foreground"><ImagePlus size={24} strokeWidth={1.7} /><span class="text-xs">미리보기를 불러올 수 없습니다.</span></div>
										{/if}
									</div>
									<dl class="grid gap-2 border-t border-border px-3 py-3 text-xs sm:grid-cols-2">
										<div class="min-w-0"><dt class="text-muted-foreground">파일 이름</dt><dd class="mt-1 truncate font-medium" title={sourceStoredAsset?.filename ?? '기존 보관함 이미지'}>{sourceStoredAsset?.filename ?? '기존 보관함 이미지'}</dd></div>
										<div><dt class="text-muted-foreground">파일 형식</dt><dd class="mt-1 font-medium">{sourceStoredAsset?.content_type ?? '알 수 없음'}</dd></div>
										<div><dt class="text-muted-foreground">파일 크기</dt><dd class="mt-1 font-medium">{sourceStoredAsset ? formatFileSize(sourceStoredAsset.size) : '저장 정보 없음'}</dd></div>
										<div><dt class="text-muted-foreground">원본 크기</dt><dd class="mt-1 font-medium" aria-live="polite">{sourceMetadataLoading ? '확인 중' : sourceDimensions ? `${sourceDimensions.width} × ${sourceDimensions.height}` : '확인 실패'}</dd></div>
									</dl>
									<OutlinedButton type="button" class="w-full rounded-none border-0 border-t" loading={sizeApplying} disabled={generating || sourceMetadataLoading || !sourceDimensions} onclick={() => void applySourceSize()}>이 사이즈 사용</OutlinedButton>
									<p class="border-t border-border px-3 py-3 text-xs text-muted-foreground">보관함 이미지를 재사용합니다. 선택한 파일은 다시 업로드하지 않습니다.</p>
								</div>
							{:else}
								<div class="flex min-h-32 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-muted/30 px-4 text-center text-muted-foreground">
									<ImagePlus size={24} strokeWidth={1.7} />
									<span class="text-xs">기기 또는 저장된 콘텐츠에서 이미지 한 장을 선택해 주세요.</span>
								</div>
							{/if}
						</div>

						<div class="space-y-2">
							<label class="block space-y-2" for="i2i-positive-prompt-prefix">
								<span class="text-sm font-medium">긍정 프롬프트 Prefix</span>
								<textarea id="i2i-positive-prompt-prefix" bind:value={positivePromptPrefix} rows="2" maxlength="5000" disabled={generating} class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"></textarea>
							</label>
							<div class="flex items-center justify-between gap-3">
								<label for="i2i-prompt" class="text-sm font-medium">긍정 프롬프트</label>
								{#if family === 'illustrious' && options.embeddings.length > 0}<OutlinedButton type="button" class="min-h-9 px-3 text-xs" disabled={generating} onclick={() => openEmbeddingPicker('positive')}>Embedding</OutlinedButton>{/if}
							</div>
							<textarea id="i2i-prompt" bind:value={prompt} rows="5" maxlength="5000" required disabled={generating} class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"></textarea>
						</div>

						<div class="space-y-2">
							<label class="block space-y-2" for="i2i-negative-prompt-prefix">
								<span class="text-sm font-medium">부정 프롬프트 Prefix</span>
								<textarea id="i2i-negative-prompt-prefix" bind:value={negativePromptPrefix} rows="2" maxlength="5000" disabled={generating} class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"></textarea>
							</label>
							<div class="flex items-center justify-between gap-3">
								<label for="i2i-negative-prompt" class="text-sm font-medium">부정 프롬프트</label>
								{#if family === 'illustrious' && options.embeddings.length > 0}<OutlinedButton type="button" class="min-h-9 px-3 text-xs" disabled={generating} onclick={() => openEmbeddingPicker('negative')}>Embedding</OutlinedButton>{/if}
							</div>
							<textarea id="i2i-negative-prompt" bind:value={negativePrompt} rows="3" maxlength="5000" disabled={generating} class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"></textarea>
						</div>

						<div class="space-y-2">
							<span class="text-sm font-medium">체크포인트</span>
							<button type="button" onclick={() => (checkpointModalOpen = true)} disabled={generating || optionsLoading || options.checkpoints.length === 0} class="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-input bg-background px-3 py-2 text-left text-sm transition hover:bg-muted disabled:pointer-events-none disabled:opacity-50">
								<span class="min-w-0 truncate">{checkpoint || '체크포인트를 선택해 주세요'}</span>
								<span class="shrink-0 text-xs font-semibold text-primary">선택</span>
							</button>
						</div>

						<div class="space-y-3">
							<div class="flex items-center justify-between gap-3">
								<span class="text-sm font-medium">LoRA <span class="text-xs font-normal text-muted-foreground">({loras.length})</span></span>
								<button type="button" onclick={() => (loraModalOpen = true)} disabled={generating || optionsLoading || options.loras.length === 0} class="rounded-md px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">LoRA 선택</button>
							</div>
							{#if loras.length === 0}
								<p class="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">사용할 LoRA가 없습니다.</p>
							{:else}
								<div class="space-y-3">
									{#each loras as lora (lora.name)}
										<div class="rounded-lg border border-border p-3">
											<p class="break-all text-sm font-medium">{lora.name}</p>
											<label class="mt-3 block space-y-2" for={`i2i-lora-strength-${lora.name}`}>
												<span class="text-sm font-medium">Strength</span>
												<input id={`i2i-lora-strength-${lora.name}`} type="number" step="0.05" bind:value={lora.strength} disabled={generating} class={numberInputClass} />
											</label>
										</div>
									{/each}
								</div>
							{/if}
						</div>

						<button type="button" onclick={() => (samplingModalOpen = true)} disabled={generating || optionsLoading || !samplerName || !scheduler} class="flex min-h-11 w-full items-center justify-between gap-4 rounded-lg border border-input bg-background px-3 py-2 text-left transition hover:bg-muted disabled:pointer-events-none disabled:opacity-50">
							<span class="text-sm font-medium">샘플러 / 스케줄러</span>
							<span class="min-w-0 truncate text-xs text-muted-foreground">{samplerName || '선택 필요'} / {scheduler || '선택 필요'}</span>
						</button>

						<div class="flex items-center justify-between gap-3">
							<span class="text-sm font-medium">이미지 크기</span>
							<IconOutlinedButton ariaLabel="가로와 세로 바꾸기" disabled={generating} onclick={swapDimensions}><ArrowLeftRight size={16} strokeWidth={1.9} /></IconOutlinedButton>
						</div>
						<div class="grid gap-4 sm:grid-cols-2">
							<label class="block space-y-2" for="i2i-width"><span class="text-sm font-medium">가로</span><input id="i2i-width" type="number" min="64" max="2048" step="8" bind:value={width} disabled={generating} class={numberInputClass} /></label>
							<label class="block space-y-2" for="i2i-height"><span class="text-sm font-medium">세로</span><input id="i2i-height" type="number" min="64" max="2048" step="8" bind:value={height} disabled={generating} class={numberInputClass} /></label>
						</div>

						<label class="block space-y-2" for="i2i-denoise">
							<span class="text-sm font-medium">Denoise</span>
							<input id="i2i-denoise" type="number" min="0" max="1" step="0.05" bind:value={denoise} disabled={generating} class={numberInputClass} />
							<span class="block text-xs text-muted-foreground">0.0은 원본을 강하게 유지하고, 1.0은 프롬프트에 따라 크게 변경합니다.</span>
						</label>

						<div class="grid gap-4 sm:grid-cols-2">
							<label class="block space-y-2" for="i2i-cfg"><span class="text-sm font-medium">CFG</span><input id="i2i-cfg" type="number" min="0" max="20" step="0.1" bind:value={cfg} disabled={generating} class={numberInputClass} /></label>
							<label class="block space-y-2" for="i2i-steps"><span class="text-sm font-medium">Steps</span><input id="i2i-steps" type="number" min="1" max="100" step="1" bind:value={steps} disabled={generating} class={numberInputClass} /></label>
						</div>

						<div class="grid gap-4 sm:grid-cols-2">
							<label class="block space-y-2" for="i2i-seed">
								<span class="text-sm font-medium">Seed</span>
								<input id="i2i-seed" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="19" bind:value={seed} disabled={generating || randomSeed} required={!randomSeed} class={numberInputClass} />
							</label>
							<label class="flex cursor-pointer items-center gap-3 self-end rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted sm:mb-0.5" for="i2i-random-seed">
								<input id="i2i-random-seed" type="checkbox" bind:checked={randomSeed} disabled={generating} class="size-4 accent-primary" />
								<span>무작위 시드</span>
							</label>
						</div>

						<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none">
							<PrimaryButton type="submit" loading={generating} disabled={optionsLoading || Boolean(optionsError) || (sourceFile ? sourceMetadataLoading || !sourceDimensions : !sourceFileId) || !checkpoint || !samplerName || !scheduler} class="w-full">
								<Sparkles size={17} strokeWidth={1.9} />
								<span>{uploading ? '소스 이미지 업로드 중' : generating ? '이미지 변환 중' : '이미지 변환'}</span>
							</PrimaryButton>
						</div>
					</form>
				</section>
			</div>
		</div>
	</Layout>

	<Modal bind:open={checkpointModalOpen} title="체크포인트 선택" description={`${familyLabel}의 전체 또는 하위 folder에서 하나를 선택하세요.`}>
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

	<Modal bind:open={loraModalOpen} title="LoRA 선택" description="전체 또는 하위 folder에서 선택하세요.">
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

	<Modal bind:open={sourceSelectionOpen} title="소스 이미지 선택" description="기기 저장소 또는 저장된 콘텐츠에서 이미지 한 장을 선택해 주세요.">
		<div class="space-y-5">
			<Tab items={selectionSourceTabs} bind:value={selectionSource} ariaLabel="소스 이미지 선택 위치" onselect={selectSelectionSource} />
			{#if selectionSource === 'device'}
				<label class="block space-y-2" for="i2i-device-file"><span class="text-sm font-medium">파일 선택</span><input id="i2i-device-file" bind:this={sourceInput} type="file" accept="image/*" class={fileInputClass} onchange={handleSourceFile} /></label>
			{:else}
				<div class="space-y-4">
					<Tab items={storedSourceTabs} bind:value={storedAssetSource} ariaLabel="저장된 이미지 종류" onselect={selectStoredAssetSource} />
					{#if storedAssetSource === 'generated'}
						<div class="space-y-2" aria-label="생성 이미지 분류">
							<Tab items={imageModelFamilyTabs} value={storedImagePreset.modelFamily} ariaLabel="생성 이미지 모델 family" onselect={selectStoredImageFamily} />
							<Tab items={imageGenerationModeTabs} value={storedImagePreset.generationMode} ariaLabel="생성 이미지 방식" onselect={selectStoredImageMode} />
						</div>
					{/if}
					<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
						<SearchBar id="i2i-stored-search" bind:value={storedSearch} label="저장 이미지 검색" placeholder="파일명으로 검색" oninput={changeStoredFilter} />
						<label class="flex items-center gap-2 text-sm" for="i2i-stored-sort"><span class="sr-only">정렬</span><select id="i2i-stored-sort" bind:value={storedSort} onchange={changeStoredFilter} class={numberInputClass}><option value="latest">최신순</option><option value="oldest">오래된순</option><option value="name">이름순</option></select></label>
					</div>
					{#if storedLoading}
						<div class="flex min-h-48 items-center justify-center"><LoadingSpinner size="md" label="저장된 이미지를 불러오는 중" /></div>
					{:else if storedAssets.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">선택할 이미지가 없습니다.</p>
					{:else}
						<div class="grid grid-cols-2 gap-3">
							{#each storedAssets as asset (asset.file_id)}
								<div class={`overflow-hidden rounded-xl border bg-card ${sourceFileId === asset.file_id ? 'border-primary ring-2 ring-primary/20' : 'border-border'}`}>
									<div class="aspect-video bg-muted">
										{#if asset.url}
											<ImageMedia source={asset.url} sourceType={imageSourceType(asset.url)} alt={storedSourceLabel(asset)} class="h-full" />
										{:else}
											<div class="flex h-full items-center justify-center text-xs text-muted-foreground">미리보기 없음</div>
										{/if}
									</div>
									<div class="space-y-2 p-2.5">
										<div class="flex items-center justify-between gap-2 text-[11px] text-muted-foreground"><span>{storedSourceLabel(asset)}</span><span>{new Date(asset.created_at).toLocaleDateString('ko-KR')}</span></div>
										<p class="truncate text-xs font-medium" title={asset.filename}>{asset.filename}</p>
										<OutlinedButton type="button" class="w-full px-2 text-xs" active={sourceFileId === asset.file_id} onclick={() => selectStoredImage(asset)}>{sourceFileId === asset.file_id ? '선택됨' : '선택'}</OutlinedButton>
									</div>
								</div>
							{/each}
						</div>
						{#if storedTotalPages > 1}
							<nav class="flex items-center justify-center gap-4 pt-2" aria-label="저장 이미지 페이지 이동">
								<button type="button" aria-label="이전 저장 이미지 페이지" disabled={storedPage <= 1} onclick={() => changeStoredPage(storedPage - 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft size={18} /></button>
								<span class="text-sm font-medium text-muted-foreground">{storedPage} / {storedTotalPages}</span>
								<button type="button" aria-label="다음 저장 이미지 페이지" disabled={storedPage >= storedTotalPages} onclick={() => changeStoredPage(storedPage + 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronRight size={18} /></button>
							</nav>
						{/if}
					{/if}
				</div>
			{/if}
		</div>
		{#snippet footer()}<OutlinedButton onclick={() => (sourceSelectionOpen = false)}>닫기</OutlinedButton>{/snippet}
	</Modal>

	<SamplingSelectionModal bind:open={samplingModalOpen} samplers={options.samplers} schedulers={options.schedulers} bind:samplerName bind:scheduler />

	<ImagePresetModal bind:open={presetOpen} preset={null} initialValues={imagePresetInitialValues()} presetType={presetType} options={options} onSaved={handlePresetSaved} />
	<Modal bind:open={presetLoadOpen} title={`${routeTitle} 프리셋 불러오기`} description="같은 T2I/I2I와 모델 family로 저장한 설정만 표시합니다." closeOnBackdrop={!presetsLoading}>
		{#if presetsLoading}
			<div class="flex justify-center py-8"><LoadingSpinner size="md" label="프리셋 불러오는 중" /></div>
		{:else if presetError}
			<p class="py-4 text-sm text-destructive" role="alert">{presetError}</p>
		{:else if presets.length === 0}
			<p class="py-4 text-sm text-muted-foreground">저장된 {routeTitle} 프리셋이 없습니다.</p>
		{:else}
			<div class="space-y-2">
				{#each presets as preset (preset.id)}
					<div class="flex items-center justify-between gap-4 rounded-xl border border-border p-3">
						<p class="min-w-0 truncate text-sm font-semibold">{preset.name}</p>
						<OutlinedButton class="shrink-0 px-3 text-xs" onclick={() => applyPreset(preset, true)}>불러오기</OutlinedButton>
					</div>
				{/each}
			</div>
		{/if}
	</Modal>

	{#if optionsError}
		<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="모델 목록 불러오기 실패" message={optionsError} onclose={() => (optionsError = '')} /></div>
	{:else if presetError}
		<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="프리셋 처리 실패" message={presetError} onclose={() => (presetError = '')} /></div>
	{:else if presetSuccess}
		<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="프리셋" message={presetSuccess} onclose={() => (presetSuccess = '')} /></div>
	{:else if sourceError}
		<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="소스 이미지 확인 실패" message={sourceError} onclose={() => (sourceError = '')} /></div>
	{:else if generationError}
		<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="이미지 변환 실패" message={generationError} onclose={() => (generationError = '')} /></div>
	{:else if successMessage}
		<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="변환 완료" message={successMessage} onclose={() => (successMessage = '')} /></div>
	{:else if infoMessage}
		<div class="fixed right-4 top-4 z-50"><Toast state="info" title="이미지 변환" message={infoMessage} onclose={() => (infoMessage = '')} /></div>
	{/if}
{/if}
