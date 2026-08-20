<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ImagePlus, Sparkles } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Select from '../../../../components/inputs/select.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import { SERVER_URL } from '$lib/configs/constants';
	import { apiJson } from '$lib/utils/api';
	import { authStore } from '$lib/stores/auth.svelte';

	type ImageOptions = {
		checkpoints: string[];
		loras: string[];
		default_checkpoint: string;
		default_lora: string | null;
	};

	type ImageGenerationStatus = {
		prompt_id: string;
		status: 'queued' | 'processing' | 'completed' | 'failed';
		images: { url: string }[];
	};

	const defaultNegativePrompt = 'worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia';
	const numberInputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const rangeInputClass = 'w-full accent-primary';

	let active = true;
	let ready = $state(false);
	let optionsLoading = $state(true);
	let optionsError = $state('');
	let generationError = $state('');
	let successMessage = $state('');
	let generating = $state(false);
	let generationStatus = $state('');
	let promptId = $state('');
	let imageUrl = $state('');
	let options = $state<ImageOptions>({
		checkpoints: [],
		loras: [],
		default_checkpoint: '',
		default_lora: null
	});
	let prompt = $state('');
	let negativePrompt = $state(defaultNegativePrompt);
	let checkpoint = $state('');
	let lora = $state('');
	let loraStrength = $state(0.7);
	let cfg = $state(4);
	let steps = $state(30);
	let width = $state(1024);
	let height = $state(1024);

	let checkpointOptions = $derived(options.checkpoints.map((value) => ({ value, label: value })));
	let loraOptions = $derived([
		{ value: '', label: 'LoRA 사용 안 함' },
		...options.loras.map((value) => ({ value, label: value }))
	]);

	onMount(() => {
		void initialize();
		return () => {
			active = false;
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
			lora = options.default_lora ?? '';
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
		if (!prompt.trim()) {
			generationError = '생성할 프롬프트를 입력해 주세요.';
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
			const queued = await apiJson<{ prompt_id: string }>('generation/image', {
				method: 'POST',
				json: {
					prompt: prompt.trim(),
					negative_prompt: negativePrompt.trim(),
					checkpoint,
					lora: lora || null,
					lora_strength: loraStrength,
					cfg,
					steps,
					width,
					height
				}
			});
			promptId = queued.prompt_id;
			await waitForResult(queued.prompt_id);
		} catch (error) {
			generationError = getErrorMessage(error);
			generationStatus = 'failed';
		} finally {
			generating = false;
		}
	}

	async function waitForResult(id: string) {
		for (let attempt = 0; attempt < 240 && active; attempt += 1) {
			const result = await apiJson<ImageGenerationStatus>(`generation/image/${id}`);
			generationStatus = result.status;
			if (result.status === 'failed') throw new Error('ComfyUI 이미지 생성에 실패했습니다.');
			if (result.status === 'completed') {
				const image = result.images[0];
				if (!image) throw new Error('생성 결과 이미지를 찾을 수 없습니다.');
				imageUrl = new URL(image.url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString();
				successMessage = '이미지 생성이 완료되었습니다.';
				return;
			}
			await new Promise((resolve) => setTimeout(resolve, 1500));
		}
		if (active) throw new Error('이미지 생성 시간이 초과되었습니다. ComfyUI 상태를 확인해 주세요.');
	}

	function getErrorMessage(error: unknown) {
		return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.';
	}
</script>

<svelte:head>
	<title>이미지 생성 · Local Field</title>
	<meta name="description" content="ComfyUI Anima 체크포인트와 LoRA를 사용한 이미지 생성" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="이미지 생성 페이지를 불러오는 중" />
	</div>
{:else}
	<Layout>
		<div class="space-y-6">
			<section class="rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8">
				<div class="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
					<div>
						<Typography as="p" variant="eyebrow">ComfyUI / Anima</Typography>
						<Typography as="h1" variant="display" class="mt-3">이미지 생성</Typography>
						<Typography as="p" variant="muted" class="mt-3 max-w-2xl text-base">
							로컬 ComfyUI의 Anima 체크포인트와 LoRA를 선택해 이미지를 생성합니다.
						</Typography>
					</div>
					<div class="inline-flex items-center gap-2 rounded-full bg-success/10 px-3 py-2 text-xs font-medium text-success">
						<span class="size-2 rounded-full bg-success"></span>
						<span>ComfyUI 연결</span>
					</div>
				</div>
			</section>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="result-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div>
							<Typography as="p" variant="muted" class="mt-1">
								{generationStatus ? `상태: ${generationStatus}` : '생성 결과가 여기에 표시됩니다.'}
							</Typography>
						</div>
						<ImagePlus size={22} class="text-primary" strokeWidth={1.8} />
					</div>

					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if imageUrl}
							<ImageMedia source={imageUrl} sourceType="server" alt="Anima 생성 결과" class="min-h-[24rem] sm:min-h-[34rem]" />
						{:else if generating}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 sm:min-h-[34rem]">
								<LoadingSpinner size="lg" label="이미지 생성 중" />
								<p class="text-sm text-muted-foreground">ComfyUI에서 이미지를 생성하고 있습니다.</p>
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
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="settings-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="settings-title"><Typography as="h2" variant="h2">생성 설정</Typography></div>
							<Typography as="p" variant="muted" class="mt-1">Anima 모델 파라미터</Typography>
						</div>
						{#if optionsLoading}<LoadingSpinner size="sm" label="모델 목록 불러오는 중" />{/if}
					</div>

					<form class="mt-6 space-y-5" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<label class="block space-y-2" for="prompt">
							<span class="text-sm font-medium">프롬프트</span>
							<textarea id="prompt" bind:value={prompt} rows="5" required placeholder="예: a beautiful anime girl standing in a flower field" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
						</label>

						<label class="block space-y-2" for="negative-prompt">
							<span class="text-sm font-medium">네거티브 프롬프트</span>
							<textarea id="negative-prompt" bind:value={negativePrompt} rows="3" class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
						</label>

						<Select id="checkpoint" label="체크포인트" options={checkpointOptions} bind:value={checkpoint} autocomplete disabled={optionsLoading || checkpointOptions.length === 0} required />
						<Select id="lora" label="LoRA" options={loraOptions} bind:value={lora} autocomplete disabled={optionsLoading} />

						<div class="grid gap-4 sm:grid-cols-2">
							<label class="block space-y-2" for="width">
								<span class="text-sm font-medium">가로</span>
								<input id="width" type="number" min="64" max="2048" step="8" bind:value={width} class={numberInputClass} />
							</label>
							<label class="block space-y-2" for="height">
								<span class="text-sm font-medium">세로</span>
								<input id="height" type="number" min="64" max="2048" step="8" bind:value={height} class={numberInputClass} />
							</label>
						</div>

						<label class="block space-y-2" for="cfg">
							<span class="flex items-center justify-between text-sm font-medium"><span>CFG</span><output>{cfg}</output></span>
							<input id="cfg" type="range" min="0" max="20" step="0.1" bind:value={cfg} class={rangeInputClass} />
						</label>
						<label class="block space-y-2" for="steps">
							<span class="flex items-center justify-between text-sm font-medium"><span>Steps</span><output>{steps}</output></span>
							<input id="steps" type="range" min="1" max="100" step="1" bind:value={steps} class={rangeInputClass} />
						</label>
						<label class="block space-y-2" for="lora-strength">
							<span class="flex items-center justify-between text-sm font-medium"><span>LoRA strength</span><output>{loraStrength}</output></span>
							<input id="lora-strength" type="range" min="-2" max="2" step="0.05" bind:value={loraStrength} disabled={!lora} class={rangeInputClass} />
						</label>

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
			<Toast state="negative" title="ComfyUI 연결 실패" message={optionsError} onclose={() => (optionsError = '')} />
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
