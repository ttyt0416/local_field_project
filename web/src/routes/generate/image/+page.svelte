<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { FolderOpen, ImagePlus, Plus, Save, Sparkles, X } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import Modal from '../../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Select from '../../../../components/inputs/select.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import { SERVER_URL } from '$lib/configs/constants';
	import { apiJson, streamSse } from '$lib/utils/api';
	import { authStore } from '$lib/stores/auth.svelte';

	type ImageOptions = {
		checkpoints: string[];
		loras: string[];
		default_checkpoint: string;
	};

	type ImageGenerationEvent = {
		prompt_id: string;
		status?: 'queued' | 'processing' | 'completed' | 'failed';
		progress?: number;
		queue_position?: number | null;
		message?: string;
		images?: { url: string }[];
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
		saved_fields: string[];
		created_at: string;
		updated_at: string;
	};
	type PresetSaveMode = 'new' | 'overwrite';

	type AspectRatio = 'custom' | '2:3' | '3:2' | '1:1' | '16:9' | '9:16';
	type ImageSize = { width: number; height: number };

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
	let enhancingPrompt = $state(false);
	let generationStatus = $state('');
	let progress = $state(0);
	let queuePosition = $state<number | null>(null);
	let promptId = $state('');
	let imageUrl = $state('');
	let generationId = $state('');
	let streamController: AbortController | null = null;
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
		checkpoints: [],
		loras: [],
		default_checkpoint: ''
	});
	let prompt = $state('');
	let promptEnhancementEnabled = $state(false);
	let improvedPrompt = $state('');
	let improvedSourcePrompt = $state('');
	let negativePrompt = $state(defaultNegativePrompt);
	let checkpoint = $state('');
	let loras = $state<LoraSelection[]>([]);
	let cfg = $state(4);
	let steps = $state(30);
	let seed = $state('');
	let aspectRatio = $state<AspectRatio>('custom');
	let width = $state(1024);
	let height = $state(1024);

	let checkpointOptions = $derived(options.checkpoints.map((value) => ({ value, label: value })));
	let loraOptions = $derived(options.loras.map((value) => ({ value, label: value })));

	$effect(() => {
		const preset = aspectRatioPresets[aspectRatio];
		if (!preset) return;
		width = preset.width;
		height = preset.height;
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
			presets = await apiJson<Preset[]>('presets?type=t2i');
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
			presets = await apiJson<Preset[]>('presets?type=t2i');
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
				json:
					presetSaveMode === 'overwrite'
						? { name: presetName.trim(), values: buildPresetValues() }
						: { type: 't2i', name: presetName.trim(), values: buildPresetValues() }
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

	function loadPreset(preset: Preset) {
		const values = preset.values;
		if (values.prompt !== undefined) prompt = values.prompt;
		if (values.negative_prompt !== undefined) negativePrompt = values.negative_prompt;
		if (values.prompt_enhancement_enabled !== undefined) promptEnhancementEnabled = values.prompt_enhancement_enabled;
		if (values.improved_prompt !== undefined) {
			improvedPrompt = values.improved_prompt;
			improvedSourcePrompt = prompt.trim();
		}
		if (values.checkpoint !== undefined) checkpoint = values.checkpoint;
		if (values.loras !== undefined) loras = values.loras.map(({ name, strength }) => ({ name, strength }));
		if (values.aspect_ratio !== undefined) aspectRatio = values.aspect_ratio;
		if (values.width !== undefined) width = values.width;
		if (values.height !== undefined) height = values.height;
		if (values.cfg !== undefined) cfg = values.cfg;
		if (values.steps !== undefined) steps = values.steps;
		loadPresetModalOpen = false;
		presetSuccess = `'${preset.name}' 프리셋을 불러왔습니다. 저장된 항목만 적용했습니다.`;
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

	onMount(() => {
		void initialize();
		return () => {
			active = false;
			streamController?.abort();
		};
	});

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		ready = true;
		try {
			options = await apiJson<ImageOptions>('generation/image/options');
			checkpoint = options.default_checkpoint;
			loras = [];
			loadGenerationParameters();
		} catch (error) {
			optionsError = getErrorMessage(error);
		} finally {
			optionsLoading = false;
		}
	}

	function loadGenerationParameters() {
		const params = page.url.searchParams;
		const queryPrompt = params.get('prompt');
		if (!queryPrompt) return;
		prompt = queryPrompt;
		negativePrompt = params.get('negative_prompt') ?? negativePrompt;
		const queryCheckpoint = params.get('checkpoint');
		if (queryCheckpoint && options.checkpoints.includes(queryCheckpoint)) checkpoint = queryCheckpoint;
		const queryLoras = params.get('loras');
		if (queryLoras) {
			try {
				const parsed = JSON.parse(queryLoras) as unknown;
				if (Array.isArray(parsed)) {
					loras = parsed
						.filter(
							(value): value is LoraSelection =>
								Boolean(value) &&
								typeof value === 'object' &&
								typeof value.name === 'string' &&
								options.loras.includes(value.name) &&
								typeof value.strength === 'number'
						)
						.map(({ name, strength }) => ({ name, strength }));
				}
			} catch {
				loras = [];
			}
		}
		const queryCfg = Number(params.get('cfg'));
		const querySteps = Number(params.get('steps'));
		const queryWidth = Number(params.get('width'));
		const queryHeight = Number(params.get('height'));
		if (Number.isFinite(queryCfg) && queryCfg >= 0 && queryCfg <= 20) cfg = queryCfg;
		if (Number.isInteger(querySteps) && querySteps >= 1 && querySteps <= 100) steps = querySteps;
		if (Number.isInteger(queryWidth) && queryWidth >= 64 && queryWidth <= 2048) width = queryWidth;
		if (Number.isInteger(queryHeight) && queryHeight >= 64 && queryHeight <= 2048) height = queryHeight;
		const querySeed = params.get('seed');
		if (querySeed && /^\d+$/.test(querySeed)) seed = querySeed;
	}

	async function generate() {
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
		if (promptEnhancementEnabled && improvedSourcePrompt !== prompt.trim()) {
			generationError = '긍정 프롬프트가 변경되었습니다. 개선을 다시 실행해 주세요.';
			return;
		}
		if (!checkpoint) {
			generationError = '체크포인트를 선택해 주세요.';
			return;
		}
		if (width % 8 !== 0 || height % 8 !== 0) {
			generationError = '이미지 가로·세로 크기는 8의 배수여야 합니다.';
			return;
		}

		generating = true;
		generationStatus = 'queued';
		try {
			const queued = await apiJson<{ prompt_id: string; client_id: string; generation_id: string }>('generation/image', {
				method: 'POST',
				json: {
					prompt: prompt.trim(),
					prompt_enhancement_enabled: promptEnhancementEnabled,
					improved_prompt: promptEnhancementEnabled ? improvedPrompt.trim() : null,
					negative_prompt: negativePrompt.trim(),
					checkpoint,
					loras: loras.filter(({ name }) => name).map(({ name, strength }) => ({ name, strength })),
					cfg,
					steps,
					width,
					height,
					seed: seed || null
				}
			});
			promptId = queued.prompt_id;
			generationId = queued.generation_id;
			await streamGeneration(queued.prompt_id, queued.client_id);
		} catch (error) {
			if (!active) return;
			generationError = getErrorMessage(error);
			generationStatus = 'failed';
		} finally {
			generating = false;
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
				timeout: 120_000,
				json: { prompt: prompt.trim() }
			});
			const resultPrompt = result.improved_prompt.contents.trim();
			if (!resultPrompt) throw new Error('개선된 프롬프트가 비어 있습니다.');
			improvedPrompt = resultPrompt;
			improvedSourcePrompt = prompt.trim();
		} catch (error) {
			promptEnhancementError = getErrorMessage(error);
		} finally {
			enhancingPrompt = false;
		}
	}

	async function streamGeneration(id: string, clientId: string) {
		const controller = new AbortController();
		streamController = controller;
		let terminalStatus = '';
		let lastError: unknown = new Error('SSE 진행 연결이 종료되었습니다.');
		try {
			for (let attempt = 0; attempt < 5 && active && !terminalStatus; attempt += 1) {
				try {
					await streamSse(
						`generation/image/${id}/events?client_id=${encodeURIComponent(clientId)}`,
						(event) => {
							const payload = JSON.parse(event.data) as ImageGenerationEvent;
							generationStatus = payload.status ?? event.event;
							if (typeof payload.progress === 'number') progress = payload.progress;
							if ('queue_position' in payload) queuePosition = payload.queue_position ?? null;
							if (event.event === 'completed') {
								terminalStatus = 'completed';
								progress = 100;
								const image = payload.images?.[0];
								if (!image) {
									terminalStatus = 'failed';
									throw new Error('생성 결과 이미지를 찾을 수 없습니다.');
								}
								imageUrl = new URL(image.url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString();
								successMessage = '이미지 생성이 완료되었습니다.';
							} else if (event.event === 'failed' || event.event === 'error') {
								terminalStatus = 'failed';
								throw new Error(payload.message ?? '이미지 생성에 실패했습니다.');
							}
						},
						{ signal: controller.signal }
					);
				} catch (error) {
					if (terminalStatus === 'failed' || !active) throw error;
					lastError = error;
				}
				if (terminalStatus || !active) break;
				if (attempt < 4) await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt));
			}
		} finally {
			if (streamController === controller) streamController = null;
		}
		if (terminalStatus === 'failed') throw lastError;
		if (terminalStatus !== 'completed' && active) throw lastError;
	}

	function imageSourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function statusLabel(status: string) {
		return {
			queued: '대기 중',
			processing: '생성 중',
			completed: '완료',
			failed: '실패'
		}[status] ?? status;
	}

	function getErrorMessage(error: unknown) {
		return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.';
	}
</script>

<svelte:head>
	<title>이미지 생성 · Local Field</title>
	<meta name="description" content="프롬프트와 파라미터를 사용한 이미지 생성" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="이미지 생성 페이지를 불러오는 중" />
	</div>
{:else}
	<Layout>
		<div class="space-y-6">
			<Typography as="h1" variant="display">이미지 생성</Typography>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="result-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div>
							<Typography as="p" variant="muted" class="mt-1">
								{#if generationStatus}
									상태: {statusLabel(generationStatus)}
									{#if generationStatus === 'queued' && queuePosition !== null} · 대기 {queuePosition}번째{/if}
									{#if generationStatus === 'processing' || generationStatus === 'completed'} · {Math.round(progress)}%{/if}
								{:else}
									생성 결과가 여기에 표시됩니다.
								{/if}
							</Typography>
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
							<IconOutlinedButton ariaLabel="프리셋 저장" loading={presetsLoading} disabled={optionsLoading || generating} onclick={() => void openSavePreset()}>
								<Save size={17} strokeWidth={1.8} />
							</IconOutlinedButton>
							<IconOutlinedButton ariaLabel="프리셋 불러오기" loading={presetsLoading} disabled={optionsLoading || generating} onclick={() => void openLoadPreset()}>
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
										<span>{enhancingPrompt ? '개선 중' : improvedSourcePrompt ? '다시 개선' : '프롬프트 개선'}</span>
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
									{#if improvedSourcePrompt && improvedSourcePrompt !== prompt.trim()}
										<p class="text-xs text-amber-600">긍정 프롬프트가 변경되었습니다. 개선을 다시 실행해 주세요.</p>
									{/if}
								</div>
							{/if}
						</div>

						<label class="block space-y-2" for="negative-prompt">
							<span class="text-sm font-medium">부정 프롬프트</span>
							<textarea id="negative-prompt" bind:value={negativePrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
						</label>

						<Select id="checkpoint" label="체크포인트" options={checkpointOptions} bind:value={checkpoint} autocomplete disabled={optionsLoading || checkpointOptions.length === 0} required />
						<div class="space-y-3">
							<div class="flex items-center justify-between gap-3">
								<span class="text-sm font-medium">LoRA</span>
								<button type="button" onclick={addLora} disabled={optionsLoading || loraOptions.length === 0 || loras.length >= loraOptions.length || loras.some((lora) => !lora.name)} class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">
									<Plus size={14} strokeWidth={2} />
									<span>LoRA 추가</span>
								</button>
							</div>
							{#if loras.length === 0}
								<p class="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">사용할 LoRA가 없습니다.</p>
							{:else}
								<div class="space-y-3">
									{#each loras as lora, index (lora.name)}
										<div class="rounded-lg border border-border p-3">
											<div class="flex items-start gap-2">
												<div class="min-w-0 flex-1">
													<Select id={`lora-${index}`} label={`LoRA ${index + 1}`} options={availableLoraOptions(index)} bind:value={lora.name} autocomplete disabled={optionsLoading} />
												</div>
												<button type="button" aria-label={`LoRA ${index + 1} 제거`} onclick={() => removeLora(index)} class="mt-7 inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
													<X size={16} strokeWidth={1.8} />
												</button>
												</div>
												{#if lora.name}
													<label class="mt-3 block space-y-2" for={`lora-strength-${index}`}>
														<span class="text-sm font-medium">Strength</span>
														<input id={`lora-strength-${index}`} type="number" min="-2" max="2" step="0.05" bind:value={lora.strength} class={numberInputClass} />
													</label>
												{/if}
										</div>
									{/each}
								</div>
							{/if}
						</div>

						<Select id="aspect-ratio" label="이미지 비율" options={aspectRatioOptions} bind:value={aspectRatio} />

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

	<Modal bind:open={savePresetModalOpen} title="프리셋 저장" description="이름과 저장할 설정 항목을 선택해 주세요." closeOnBackdrop={!savingPreset}>
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

	<Modal bind:open={loadPresetModalOpen} title="프리셋 불러오기" description="선택한 프리셋의 저장 항목만 현재 설정에 적용합니다." closeOnBackdrop={!presetsLoading}>
		{#if presetsLoading}
			<div class="flex justify-center py-8"><LoadingSpinner size="md" label="프리셋 불러오는 중" /></div>
		{:else if presetError}
			<p class="py-4 text-sm text-destructive" role="alert">{presetError}</p>
		{:else if presets.length === 0}
			<p class="py-4 text-sm text-muted-foreground">저장된 t2i 프리셋이 없습니다.</p>
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
