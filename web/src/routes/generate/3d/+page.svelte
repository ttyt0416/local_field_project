<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Box, ImagePlus, Sparkles, X } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import ModelViewer from '../../../../components/media/model-viewer.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { generationJobStore, type GenerationJobStatus } from '$lib/stores/generation-jobs.svelte';
	import { apiForm } from '$lib/utils/api';
	import { formatElapsedSeconds } from '$lib/utils/generation';

	type ModelPreset = 'preview' | 'standard' | 'high';
	type Accepted3DGeneration = {
		prompt_id: string;
		client_id: string;
		generation_id: string;
		status: 'queued' | 'processing';
		stage?: string;
		progress: number;
		created_at: string;
		elapsed_seconds: number;
		preset: ModelPreset;
		seed: number | null;
	};

	const presetTabs = [
		{ value: 'preview' as const, label: '미리보기' },
		{ value: 'standard' as const, label: '표준' },
		{ value: 'high' as const, label: '고품질' }
	];
	const presetDescriptions: Record<ModelPreset, string> = {
		preview: '형태와 구도를 빠르게 확인합니다.',
		standard: '품질과 생성 시간의 균형을 맞춥니다.',
		high: '더 세밀한 3D 결과를 생성합니다.'
	};
	const stageLabels: Record<string, string> = {
		queued: '생성 대기 중',
		preparing: '작업 준비 중',
		preprocessing: '소스 이미지 전처리 중',
		background_removal: '배경 제거 중',
		background_cleanup: '배경과 오브젝트 경계 정리 중',
		conditioning: '3D 조건 분석 중',
		structure: '3D 구조 생성 중',
		shape: '3D 형상 생성 중',
		sampling: '3D 구조 생성 중',
		decoding: '3D 표현 변환 중',
		texture: '텍스처 생성 중',
		mesh: '메시 생성 중',
		mesh_extraction: '메시 추출 중',
		texture_baking: '텍스처 생성 중',
		storage: '모델 파일 저장 중',
		exporting: '모델 파일 내보내는 중',
		completed: '3D 모델 생성 완료'
	};
	const inputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const fileClass = 'block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary';

	let ready = $state(false);
	let sourceFile = $state<File | null>(null);
	let sourceInput = $state<HTMLInputElement>();
	let preset = $state<ModelPreset>('standard');
	let seed = $state('');
	let randomSeed = $state(true);
	let removeBackground = $state(true);
	let padding = $state(1.1);
	let generating = $state(false);
	let uploading = $state(false);
	let cancelling = $state(false);
	let status = $state<GenerationJobStatus | ''>('');
	let stage = $state('');
	let elapsedSeconds = $state(0);
	let modelUrl = $state('');
	let generationId = $state('');
	let jobKey = $state('');
	let error = $state('');
	let success = $state('');
	let announcedTerminal = $state('');
	let active = true;

	onMount(() => {
		void initialize();
		return () => {
			active = false;
		};
	});

	$effect(() => {
		const now = generationJobStore.now;
		const job = jobKey ? generationJobStore.jobs[jobKey] : undefined;
		if (!job) {
			elapsedSeconds = 0;
			return;
		}
		status = job.status;
		stage = job.stage ?? stage;
		elapsedSeconds = generationJobStore.elapsedSeconds(job, now);
		modelUrl = job.modelUrl ?? '';
		generationId = job.generationId;
		const terminalKey = `${jobKey}:${job.status}`;
		if (job.status === 'completed' && announcedTerminal !== terminalKey) {
			success = '3D 모델 생성이 완료되었습니다.';
			announcedTerminal = terminalKey;
		}
		if (job.status === 'failed' && announcedTerminal !== terminalKey) {
			error = job.error ?? '3D 모델 생성에 실패했습니다.';
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
		ready = true;
	}

	function handleSourceFile(event: Event) {
		if (!(event.currentTarget instanceof HTMLInputElement)) return;
		sourceFile = event.currentTarget.files?.[0] ?? null;
	}

	function clearSource() {
		sourceFile = null;
		if (sourceInput) sourceInput.value = '';
	}

	function stageLabel(value: string, currentStatus: GenerationJobStatus | '') {
		if (currentStatus === 'queued') return stageLabels.queued;
		if (currentStatus === 'completed') return stageLabels.completed;
		if (currentStatus === 'cancelled') return '생성이 취소되었습니다.';
		if (currentStatus === 'failed') return '생성에 실패했습니다.';
		return stageLabels[value] ?? (value ? value.replaceAll('_', ' ') : '3D 모델 생성 중');
	}

	async function generate() {
		jobKey = '';
		announcedTerminal = '';
		error = '';
		success = '';
		modelUrl = '';
		generationId = '';
		status = 'queued';
		stage = 'queued';
		if (!sourceFile) {
			error = '3D 모델로 변환할 이미지를 선택해 주세요.';
			return;
		}
		const parsedSeed = randomSeed ? null : Number(seed);
		if (!randomSeed && (!seed.trim() || typeof parsedSeed !== 'number' || !Number.isSafeInteger(parsedSeed) || parsedSeed < 0)) {
			error = 'Seed는 0 이상의 정수로 입력해 주세요.';
			return;
		}
		const parsedPadding = Number(padding);
		if (!Number.isFinite(parsedPadding) || parsedPadding < 1 || parsedPadding > 1.5) {
			error = '여백은 1.0에서 1.5 사이로 입력해 주세요.';
			return;
		}

		const form = new FormData();
		form.append('files', sourceFile, sourceFile.name);
		form.append('payload', JSON.stringify({
			source: { file_index: 0 },
			preset,
			seed: parsedSeed,
			remove_background: removeBackground,
			padding: parsedPadding
		}));
		generating = true;
		uploading = true;
		try {
			const accepted = await apiForm<Accepted3DGeneration>('generation/3d', form, { timeout: 120_000 });
			uploading = false;
			jobKey = generationJobStore.track({
				kind: '3d',
				promptId: accepted.prompt_id,
				clientId: accepted.client_id,
				generationId: accepted.generation_id,
				preset: accepted.preset,
				seed: accepted.seed,
				status: accepted.status,
				progress: accepted.progress,
				stage: accepted.stage ?? accepted.status,
				createdAt: Date.parse(accepted.created_at) || Date.now(),
				elapsedSeconds: accepted.elapsed_seconds
			});
			await generationJobStore.waitForTerminal(jobKey);
		} catch (reason) {
			if (active) {
				error = reason instanceof Error ? reason.message : '3D 모델 생성을 시작하지 못했습니다.';
				status = 'failed';
			}
		} finally {
			uploading = false;
			generating = false;
		}
	}

	async function cancelGeneration() {
		if (!jobKey || !generating || cancelling) return;
		cancelling = true;
		error = '';
		try {
			await generationJobStore.cancel(jobKey);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '3D 모델 생성을 취소하지 못했습니다.';
		} finally {
			cancelling = false;
		}
	}
</script>

<svelte:head>
	<title>3D 모델 생성 · Local Field</title>
	<meta name="description" content="TRELLIS.2 이미지 기반 3D 모델 생성" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="3D 모델 생성 페이지를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div>
				<Typography as="h1" variant="display">3D 모델 생성</Typography>
				<Typography as="p" variant="muted" class="mt-2">한 장의 이미지에서 TRELLIS.2 3D 모델을 생성합니다.</Typography>
			</div>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="model-result-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="model-result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div>
							{#if status}<Typography as="p" variant="muted" class="mt-1">{stageLabel(stage, status)} · {status === 'queued' || status === 'processing' ? '경과' : '소요'} {formatElapsedSeconds(elapsedSeconds)}</Typography>{/if}
						</div>
						<Box size={22} class="text-primary" strokeWidth={1.8} />
					</div>
					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if modelUrl}
							<ModelViewer source={modelUrl} sourceType="server" alt="생성된 3D 모델" autoRotate class="min-h-[24rem] sm:min-h-[34rem]" />
						{:else if generating}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 px-6 text-center sm:min-h-[34rem]">
								<LoadingSpinner size="lg" label={uploading ? '소스 이미지 업로드 중' : stageLabel(stage, status)} />
								<p class="text-sm font-medium text-foreground">{uploading ? '이미지를 업로드하고 있습니다.' : stageLabel(stage, status)}</p>
								<p class="text-xs leading-5 text-muted-foreground">단계마다 작업량이 달라 정확하지 않은 단일 진행률 대신 현재 처리 단계를 표시합니다.</p>
								<p class="text-lg font-semibold tabular-nums text-primary">경과 {formatElapsedSeconds(elapsedSeconds)}</p>
							</div>
						{:else}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-3 px-6 text-center sm:min-h-[34rem]"><div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Box size={26} strokeWidth={1.7} /></div><p class="text-sm font-medium">아직 생성된 3D 모델이 없습니다.</p><p class="max-w-sm text-xs leading-5 text-muted-foreground">소스 이미지를 선택하고 생성 설정을 확인한 뒤 생성 버튼을 눌러 주세요.</p></div>
						{/if}
					</div>
					{#if generating && jobKey}
						<OutlinedButton class="mt-4 w-full" loading={cancelling} disabled={cancelling} onclick={() => void cancelGeneration()}><X size={16} strokeWidth={1.9} /><span>{cancelling ? '3D 생성 취소 중' : '3D 생성 취소'}</span></OutlinedButton>
					{/if}
					{#if modelUrl && generationId}
						<a href={`/vault/3d/${generationId}`} class="mt-4 inline-flex text-sm font-semibold text-primary hover:underline">보관함에서 상세 보기</a>
					{/if}
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="model-settings-title">
					<div id="model-settings-title"><Typography as="h2" variant="h2">3D 생성 설정</Typography></div>
					<form class="mt-5 space-y-5 pb-24 sm:pb-0" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<div class="space-y-3">
							<label for="model-source" class="text-sm font-medium">소스 이미지</label>
							<input id="model-source" bind:this={sourceInput} type="file" accept="image/*" class={fileClass} disabled={generating} onchange={handleSourceFile} />
							{#if sourceFile}
								<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
									<OutlinedButton class="absolute right-2 top-2 z-10 min-h-8 bg-card/90 px-2 text-xs" disabled={generating} onclick={clearSource}><X size={14} />선택 해제</OutlinedButton>
									<ImageMedia source={sourceFile} sourceType="local" alt="선택한 3D 소스 이미지" class="max-h-72" />
									<p class="border-t border-border px-3 py-2 text-xs text-muted-foreground">{sourceFile.name}</p>
								</div>
							{:else}
								<div class="flex min-h-32 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-muted/30 text-muted-foreground"><ImagePlus size={24} strokeWidth={1.7} /><span class="text-xs">기기에서 이미지를 선택해 주세요.</span></div>
							{/if}
						</div>

						<div class="space-y-2">
							<span class="text-sm font-medium">품질 프리셋</span>
							<Tab items={presetTabs} bind:value={preset} ariaLabel="3D 품질 프리셋" />
							<p class="text-xs text-muted-foreground">{presetDescriptions[preset]}</p>
						</div>

						<label class="flex items-center justify-between gap-4 rounded-xl border border-border px-3 py-3 text-sm" for="model-remove-background"><span><span class="block font-medium">배경 제거</span><span class="mt-1 block text-xs text-muted-foreground">오브젝트 중심의 3D 모델을 만들도록 배경을 제거합니다.</span></span><input id="model-remove-background" type="checkbox" bind:checked={removeBackground} disabled={generating} class="size-4 accent-primary" /></label>

						<label class="block space-y-2" for="model-padding"><span class="text-sm font-medium">오브젝트 여백</span><input id="model-padding" type="number" min="1" max="1.5" step="0.01" bind:value={padding} disabled={generating} class={inputClass} /><span class="block text-xs text-muted-foreground">배경 제거 후 오브젝트 주변에 적용할 여백입니다. (1.0–1.5)</span></label>

						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="model-seed"><span class="text-sm font-medium">Seed</span><input id="model-seed" type="number" min="0" step="1" bind:value={seed} disabled={generating || randomSeed} required={!randomSeed} class={inputClass} /></label><label class="flex cursor-pointer items-center gap-3 self-end rounded-lg border border-border px-3 py-2.5 text-sm transition" for="random-model-seed"><input id="random-model-seed" type="checkbox" bind:checked={randomSeed} disabled={generating} class="size-4 accent-primary" /><span>무작위 시드</span></label></div>

						<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"><PrimaryButton type="submit" loading={generating} disabled={!sourceFile} class="w-full"><Sparkles size={17} strokeWidth={1.9} /><span>{generating ? '3D 생성 중' : '3D 모델 생성'}</span></PrimaryButton></div>
					</form>
				</section>
			</div>
		</div>
	</Layout>

	{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="3D 모델 생성 실패" message={error} onclose={() => (error = '')} /></div>{:else if success}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="생성 완료" message={success} onclose={() => (success = '')} /></div>{/if}
{/if}
