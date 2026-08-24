<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ImagePlus, Plus, Sparkles, X } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
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

	let active = true;
	let ready = $state(false);
	let optionsLoading = $state(true);
	let optionsError = $state('');
	let generationError = $state('');
	let successMessage = $state('');
	let generating = $state(false);
	let generationStatus = $state('');
	let progress = $state(0);
	let queuePosition = $state<number | null>(null);
	let streamConnected = $state(false);
	let promptId = $state('');
	let imageUrl = $state('');
	let generationId = $state('');
	let streamController: AbortController | null = null;
	let options = $state<ImageOptions>({
		checkpoints: [],
		loras: [],
		default_checkpoint: ''
	});
	let prompt = $state('');
	let negativePrompt = $state(defaultNegativePrompt);
	let checkpoint = $state('');
	let loras = $state<LoraSelection[]>([]);
	let cfg = $state(4);
	let steps = $state(30);
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
		loras = [...loras, { name: '', strength: 0.7 }];
	}

	function removeLora(index: number) {
		loras = loras.filter((_, currentIndex) => currentIndex !== index);
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
			loras = options.loras.length > 0 ? [{ name: '', strength: 0.7 }] : [];
		} catch (error) {
			optionsError = getErrorMessage(error);
		} finally {
			optionsLoading = false;
		}
	}

	async function generate() {
		generationError = '';
		successMessage = '';
		imageUrl = '';
		generationId = '';
		progress = 0;
		queuePosition = null;
		streamConnected = false;
		if (!prompt.trim()) {
			generationError = '생성할 프롬프트를 입력해 주세요.';
			return;
		}
		if (!checkpoint) {
			generationError = '체크포인트를 선택해 주세요.';
			return;
		}
		if (loras.some((lora) => !lora.name)) {
			generationError = '추가한 LoRA를 선택해 주세요.';
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
					negative_prompt: negativePrompt.trim(),
					checkpoint,
					loras: loras.filter(({ name }) => name).map(({ name, strength }) => ({ name, strength })),
					cfg,
					steps,
					width,
					height
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
						{ signal: controller.signal, onConnected: () => (streamConnected = true) }
					);
				} catch (error) {
					if (terminalStatus === 'failed' || !active) throw error;
					lastError = error;
				}
				if (terminalStatus || !active) break;
				streamConnected = false;
				if (attempt < 4) await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt));
			}
		} finally {
			streamConnected = false;
			if (streamController === controller) streamController = null;
		}
		if (terminalStatus === 'failed') throw lastError;
		if (terminalStatus !== 'completed' && active) throw lastError;
	}

	function statusLabel(status: string) {
		return {
			queued: '대기 중',
			processing: '생성 중',
			completed: '완료',
			failed: '실패',
			connecting: '연결 중'
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
									{#if generating} · {streamConnected ? 'SSE 연결됨' : 'SSE 연결 중'}{/if}
								{:else}
									생성 결과가 여기에 표시됩니다.
								{/if}
							</Typography>
						</div>
						<ImagePlus size={22} class="text-primary" strokeWidth={1.8} />
					</div>

					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if imageUrl}
							<ImageMedia source={imageUrl} sourceType="server" alt="생성 결과" class="min-h-[24rem] sm:min-h-[34rem]" />
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
						{#if optionsLoading}<LoadingSpinner size="sm" label="모델 목록 불러오는 중" />{/if}
					</div>

					<form class="mt-6 space-y-5" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<label class="block space-y-2" for="prompt">
							<span class="text-sm font-medium">긍정 프롬프트</span>
							<textarea id="prompt" bind:value={prompt} rows="5" required class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
						</label>

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
												<label class="mt-3 block space-y-2" for={`lora-strength-${index}`}>
												<span class="text-sm font-medium">Strength</span>
												<input id={`lora-strength-${index}`} type="number" min="-2" max="2" step="0.05" bind:value={lora.strength} class={numberInputClass} />
												</label>
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

						<PrimaryButton type="submit" loading={generating} disabled={optionsLoading || !checkpoint} class="w-full">
							<Sparkles size={17} strokeWidth={1.9} />
							<span>{generating ? '생성 중' : '이미지 생성'}</span>
						</PrimaryButton>
					</form>
				</section>
			</div>
		</div>
	</Layout>

	{#if optionsError}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="모델 목록 불러오기 실패" message={optionsError} onclose={() => (optionsError = '')} />
		</div>
	{:else if generationError}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="이미지 생성 실패" message={generationError} onclose={() => (generationError = '')} />
		</div>
	{:else if successMessage}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="positive" title="생성 완료" message={successMessage} onclose={() => (successMessage = '')} />
		</div>
	{/if}
{/if}
