<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { ArrowLeftRight, Check, ImagePlus, Sparkles, X } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import Modal from '../../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import SamplingSelectionModal from '../../../../components/presets/sampling-selection-modal.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { imageGenerationStore, type ImageGenerationParameters } from '$lib/stores/image-generation.svelte';
	import { apiForm, apiJson } from '$lib/utils/api';
	import { formatElapsedSeconds, formatFileSize } from '$lib/utils/generation';

	type ImageFamily = 'anima' | 'illustrious';
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

	const defaultNegativePrompt = 'worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia';
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

	let family = $derived<ImageFamily>(page.url.searchParams.get('family') === 'illustrious' ? 'illustrious' : 'anima');
	let familyLabel = $derived(family === 'illustrious' ? 'Illustrious' : 'Anima');
	let routeTitle = $derived(`이미지를 이미지로 (${familyLabel})`);

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
	let prompt = $state('');
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
		optionsLoading = true;
		optionsError = '';
		checkpointModalOpen = false;
		loraModalOpen = false;
		samplingModalOpen = false;
		options = { ...emptyOptions };
		checkpoint = '';
		loras = [];
		samplerName = '';
		scheduler = '';
		try {
			const loaded = await apiJson<ImageOptions>(`generation/image/options?family=${targetFamily}`);
			if (!active || requestId !== optionsRequestId || family !== targetFamily) return;
			options = loaded;
			checkpoint = loaded.default_checkpoint;
			samplerName = loaded.default_sampler;
			scheduler = loaded.default_scheduler;
			if (regenerationParameters) {
				applyGenerationParameters(regenerationParameters);
				regenerationParameters = null;
			}
		} catch (error) {
			if (active && requestId === optionsRequestId) optionsError = getErrorMessage(error);
		} finally {
			if (active && requestId === optionsRequestId) optionsLoading = false;
		}
	}

	function applyGenerationParameters(parameters: ImageGenerationParameters) {
		if (parameters.generation_mode !== 'i2i' || (parameters.model_family && parameters.model_family !== family)) return;
		prompt = parameters.prompt;
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
	}

	function handleSourceFile(event: Event) {
		if (!(event.currentTarget instanceof HTMLInputElement) || generating) return;
		const files = event.currentTarget.files;
		if (!files || files.length === 0) {
			clearSource();
			return;
		}
		if (files.length !== 1) {
			sourceError = '소스 이미지는 정확히 한 장만 선택해 주세요.';
			clearSource();
			return;
		}
		const file = files[0];
		if (!file.type.startsWith('image/')) {
			sourceError = '이미지 파일만 선택할 수 있습니다.';
			clearSource();
			return;
		}
		if (file.size <= 0) {
			sourceError = '비어 있는 이미지 파일은 사용할 수 없습니다.';
			clearSource();
			return;
		}
		sourceError = '';
		sourceFile = file;
		sourceFileId = '';
		sourceImageUrl = '';
		sourceDimensions = null;
		void inspectSourceImage(file);
	}

	async function inspectSourceImage(file: File) {
		const requestId = ++sourceMetadataRequestId;
		sourceMetadataLoading = true;
		try {
			const dimensions = await readImageDimensions(file);
			if (!active || requestId !== sourceMetadataRequestId || sourceFile !== file) return;
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

	function readImageDimensions(file: File) {
		const objectUrl = URL.createObjectURL(file);
		return new Promise<ImageDimensions>((resolve, reject) => {
			const image = new Image();
			image.onload = () => {
				URL.revokeObjectURL(objectUrl);
				if (image.naturalWidth > 0 && image.naturalHeight > 0) {
					resolve({ width: image.naturalWidth, height: image.naturalHeight });
				} else {
					reject(new Error('invalid image dimensions'));
				}
			};
			image.onerror = () => {
				URL.revokeObjectURL(objectUrl);
				reject(new Error('image metadata unavailable'));
			};
			image.src = objectUrl;
		});
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
		if (!sourceFile || sizeApplying || generating) return;
		sizeApplying = true;
		sourceError = '';
		try {
			const dimensions = sourceDimensions ?? (await readImageDimensions(sourceFile));
			if (sourceFile) sourceDimensions = dimensions;
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
		sourceDimensions = null;
		sourceMetadataLoading = false;
		sizeApplying = false;
		if (sourceInput) sourceInput.value = '';
	}

	function toggleLora(name: string) {
		if (generating) return;
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

	function validateInputs() {
		if (optionsLoading) return '모델 목록을 불러오는 중입니다.';
		if (optionsError) return '모델 목록을 다시 불러온 뒤 시도해 주세요.';
		if (!sourceFile && !sourceFileId) return '변환할 소스 이미지를 선택해 주세요.';
		if (sourceFile && (!sourceFile.type.startsWith('image/') || sourceFile.size <= 0)) return '유효한 이미지 파일을 선택해 주세요.';
		if (sourceFile && sourceMetadataLoading) return '소스 이미지 정보를 확인하는 중입니다.';
		if (sourceFile && !sourceDimensions) return '원본 크기를 확인할 수 있는 이미지를 선택해 주세요.';
		if (!prompt.trim()) return '생성할 프롬프트를 입력해 주세요.';
		if (prompt.trim().length > 5000) return '긍정 프롬프트는 5,000자 이하로 입력해 주세요.';
		if (negativePrompt.trim().length > 5000) return '부정 프롬프트는 5,000자 이하로 입력해 주세요.';
		if (!checkpoint || !options.checkpoints.includes(checkpoint)) return '체크포인트를 선택해 주세요.';
		if (loras.length > 8 || new Set(loras.map(({ name }) => name)).size !== loras.length) return 'LoRA 선택을 확인해 주세요.';
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
			prompt: prompt.trim(),
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
			<div>
				<Typography as="h1" variant="display">{routeTitle}</Typography>
				<Typography as="p" variant="muted" class="mt-2">기기에서 이미지 한 장을 선택하고 {familyLabel} 모델로 새 이미지를 생성합니다. 선택만으로는 파일을 업로드하지 않습니다.</Typography>
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
						{#if optionsLoading}<LoadingSpinner size="sm" label="모델 목록 불러오는 중" />{/if}
					</div>

					<form class="mt-6 space-y-5 pb-24 sm:pb-0" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<div class="space-y-3">
							<label for="i2i-source" class="text-sm font-medium">소스 이미지</label>
							<input id="i2i-source" bind:this={sourceInput} type="file" accept="image/*" class={fileInputClass} disabled={generating} onchange={handleSourceFile} />
							{#if sourceFile}
								<div class="overflow-hidden rounded-xl border border-border bg-muted/30">
									<div class="relative">
										<IconOutlinedButton ariaLabel="소스 이미지 선택 해제" title="소스 이미지 선택 해제" class="absolute right-2 top-2 z-10 bg-card/90" disabled={generating} onclick={() => clearSource()}>
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
							{:else if sourceImageUrl}
								<div class="overflow-hidden rounded-xl border border-border bg-muted/30">
									<div class="relative">
										<IconOutlinedButton ariaLabel="소스 이미지 선택 해제" title="소스 이미지 선택 해제" class="absolute right-2 top-2 z-10 bg-card/90" disabled={generating} onclick={() => clearSource()}><X size={16} strokeWidth={2} /></IconOutlinedButton>
										<ImageMedia source={sourceImageUrl} sourceType={imageSourceType(sourceImageUrl)} alt="기존 I2I 소스 이미지" class="max-h-80" />
									</div>
									<p class="border-t border-border px-3 py-3 text-xs text-muted-foreground">기존 보관함 이미지를 재사용합니다. 출력 크기는 저장된 생성 설정을 유지합니다.</p>
								</div>
							{:else}
								<div class="flex min-h-32 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-muted/30 px-4 text-center text-muted-foreground">
									<ImagePlus size={24} strokeWidth={1.7} />
									<span class="text-xs">기기에서 이미지 한 장을 선택해 주세요.</span>
								</div>
							{/if}
						</div>

						<div class="space-y-2">
							<div class="flex items-center justify-between gap-3">
								<label for="i2i-prompt" class="text-sm font-medium">긍정 프롬프트</label>
								{#if family === 'illustrious' && options.embeddings.length > 0}<OutlinedButton type="button" class="min-h-9 px-3 text-xs" disabled={generating} onclick={() => openEmbeddingPicker('positive')}>Embedding</OutlinedButton>{/if}
							</div>
							<textarea id="i2i-prompt" bind:value={prompt} rows="5" maxlength="5000" required disabled={generating} class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"></textarea>
						</div>

						<div class="space-y-2">
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
								<span class="text-sm font-medium">LoRA <span class="text-xs font-normal text-muted-foreground">({loras.length}/8)</span></span>
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

	<Modal bind:open={checkpointModalOpen} title="체크포인트 선택" description={`${familyLabel}에서 사용할 설치된 체크포인트를 하나 선택하세요.`}>
		<div class="grid max-h-[60dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
			{#each options.checkpoints as value}
				<button type="button" onclick={() => { checkpoint = value; checkpointModalOpen = false; }} aria-pressed={checkpoint === value} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${checkpoint === value ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}>
					<span>{value}</span>
					{#if checkpoint === value}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}
				</button>
			{/each}
		</div>
	</Modal>

	<Modal bind:open={loraModalOpen} title="LoRA 선택" description="설치된 LoRA를 최대 8개까지 선택하거나 선택 해제하세요.">
		<div class="grid max-h-[60dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
			{#each options.loras as value}
				{@const selected = loras.some((lora) => lora.name === value)}
				<button type="button" onclick={() => toggleLora(value)} aria-pressed={selected} class={`flex min-h-14 items-center justify-between gap-2 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${selected ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}>
					<span>{value}</span>
					{#if selected}<Check size={15} class="shrink-0" strokeWidth={2} />{/if}
				</button>
			{/each}
		</div>
		{#snippet footer()}<PrimaryButton onclick={() => (loraModalOpen = false)}>선택 완료</PrimaryButton>{/snippet}
	</Modal>

	<Modal bind:open={embeddingModalOpen} title={`${embeddingTarget === 'positive' ? '긍정' : '부정'} 프롬프트 Embedding`} description="선택한 Embedding 토큰을 프롬프트에 추가합니다.">
		<div class="grid max-h-[60dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
			{#each options.embeddings as value}
				<button type="button" onclick={() => insertEmbedding(value)} class="min-h-14 break-all rounded-lg border border-border px-3 py-2 text-left text-xs transition hover:bg-muted">{value}</button>
			{/each}
		</div>
	</Modal>

	<SamplingSelectionModal bind:open={samplingModalOpen} samplers={options.samplers} schedulers={options.schedulers} bind:samplerName bind:scheduler />

	{#if optionsError}
		<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="모델 목록 불러오기 실패" message={optionsError} onclose={() => (optionsError = '')} /></div>
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
