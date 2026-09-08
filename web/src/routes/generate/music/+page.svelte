<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { AudioLines, Download, Music, Sparkles, X } from '@lucide/svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { apiJson } from '$lib/utils/api';
	import { downloadMedia } from '$lib/utils/download';

	type MusicGenerationOptions = {
		model: 'MiniMax-Music3';
		service_available: boolean;
		detail: string;
		default_duration_seconds: number;
		max_duration_seconds: number;
	};
	type MusicOutput = { url: string; filename: string; content_type: string; duration_seconds?: number | null; size_bytes?: number | null };
	type MusicGenerationStatus = {
		prompt_id: string;
		generation_id: string;
		status: string;
		progress: number;
		queue_position?: number | null;
		seed?: number | null;
		requested_duration_seconds: number;
		created_at?: string | null;
		elapsed_seconds: number;
		audio?: MusicOutput | null;
	};
	type MusicGenerationAccepted = {
		prompt_id: string;
		client_id: string;
		generation_id: string;
		status: 'queued';
		seed: number;
		duration_seconds: number;
		created_at: string;
		elapsed_seconds: number;
	};

	const textareaClass = 'w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60';
	const inputClass = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60';

	let ready = $state(false);
	let optionsLoading = $state(true);
	let model = $state<MusicGenerationOptions['model']>('MiniMax-Music3');
	let serviceAvailable = $state(false);
	let serviceDetail = $state('');
	let maxDurationSeconds = $state(300);
	let description = $state('');
	let lyrics = $state('');
	let durationSeconds = $state(60);
	let seed = $state<number | undefined>(undefined);
	let generating = $state(false);
	let cancelling = $state(false);
	let downloading = $state(false);
	let jobKey = $state('');
	let status = $state('');
	let progress = $state(0);
	let queuePosition = $state<number | null>(null);
	let elapsedSeconds = $state(0);
	let audioUrl = $state('');
	let audioFilename = $state('');
	let audioSizeBytes = $state<number | null>(null);
	let error = $state('');
	let notice = $state('');
	let announcedTerminal = $state('');

	onMount(() => {
		void initialize();
	});

	$effect(() => {
		const job = jobKey ? generationJobStore.jobs[jobKey] : undefined;
		if (!job) return;
		status = job.status;
		progress = job.progress;
		queuePosition = job.queuePosition;
		elapsedSeconds = job.elapsedSeconds;
		audioUrl = job.audioUrl ?? audioUrl;
		audioFilename = job.audioFilename ?? audioFilename;
		audioSizeBytes = job.audioSizeBytes ?? audioSizeBytes;
		if (job.error) error = job.error;
		const terminalKey = `${jobKey}:${job.status}`;
		if (job.status === 'completed' && announcedTerminal !== terminalKey) {
			announcedTerminal = terminalKey;
			generating = false;
			notice = '음악 생성이 완료되었습니다.';
		}
		if (job.status === 'failed' && announcedTerminal !== terminalKey) {
			announcedTerminal = terminalKey;
			generating = false;
			error = job.error || '음악 생성에 실패했습니다.';
		}
		if (job.status === 'cancelled') generating = false;
	});

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		await generationJobStore.initialize();
		try {
			const [options, latest] = await Promise.all([
				apiJson<MusicGenerationOptions>('generation/music/options'),
				apiJson<MusicGenerationStatus | null>('generation/music/latest')
			]);
			model = options.model;
			serviceAvailable = options.service_available;
			serviceDetail = options.detail;
			durationSeconds = options.default_duration_seconds;
			maxDurationSeconds = options.max_duration_seconds;
			if (latest) restoreLatest(latest);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '음악 생성 설정을 불러오지 못했습니다.';
		} finally {
			optionsLoading = false;
			ready = true;
		}
	}

	function restoreLatest(latest: MusicGenerationStatus) {
		status = latest.status;
		progress = latest.progress;
		queuePosition = latest.queue_position ?? null;
		elapsedSeconds = latest.elapsed_seconds;
		seed = latest.seed ?? undefined;
		durationSeconds = latest.requested_duration_seconds;
		audioUrl = latest.audio?.url ?? '';
		audioFilename = latest.audio?.filename ?? '';
		audioSizeBytes = latest.audio?.size_bytes ?? null;
		if (latest.status === 'queued' || latest.status === 'processing') {
			jobKey = `music:${latest.prompt_id}`;
			generating = true;
		}
	}

	async function generate() {
		if (!serviceAvailable || !description.trim() || generating) return;
		generating = true;
		status = 'queued';
		progress = 0;
		queuePosition = null;
		elapsedSeconds = 0;
		audioUrl = '';
		audioFilename = '';
		audioSizeBytes = null;
		error = '';
		notice = '';
		try {
			const accepted = await apiJson<MusicGenerationAccepted>('generation/music', {
				method: 'POST',
				json: {
					description: description.trim(),
					lyrics,
					duration_seconds: durationSeconds,
					seed: seed ?? null
				}
			});
			seed = accepted.seed;
			jobKey = generationJobStore.track({
				kind: 'music',
				promptId: accepted.prompt_id,
				clientId: accepted.client_id,
				generationId: accepted.generation_id,
				seed: accepted.seed,
				status: accepted.status,
				createdAt: Date.parse(accepted.created_at),
				elapsedSeconds: accepted.elapsed_seconds
			});
		} catch (reason) {
			generating = false;
			status = '';
			error = reason instanceof Error ? reason.message : '음악 생성을 시작하지 못했습니다.';
		}
	}

	async function cancelGeneration() {
		if (!jobKey || !generating || cancelling) return;
		cancelling = true;
		try {
			await generationJobStore.cancel(jobKey);
			notice = '음악 생성을 취소했습니다.';
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '음악 생성을 취소하지 못했습니다.';
		} finally {
			cancelling = false;
		}
	}

	async function downloadMusic() {
		if (!audioUrl || downloading) return;
		downloading = true;
		try {
			await downloadMedia(audioUrl, audioFilename || 'local-field-music.flac');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '음악을 다운로드하지 못했습니다.';
		} finally {
			downloading = false;
		}
	}

	function statusLabel(value: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패', cancelled: '취소됨' }[value] ?? value;
	}

	function formatElapsed(value: number) {
		const seconds = Math.max(0, Math.floor(value));
		return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
	}

	function formatBytes(value: number | null) {
		if (!value) return '';
		return `${(value / 1024 / 1024).toFixed(1)} MB`;
	}
</script>

<svelte:head>
	<title>음악 생성 · Local Field</title>
	<meta name="description" content="MiniMax-Music3 local 음악 생성" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="음악 생성 페이지를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<Typography as="h1" variant="display">음악 생성</Typography>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="min-w-0 rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="music-result-title">
					<div class="flex items-center justify-between gap-4"><div id="music-result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div><AudioLines size={22} class="text-primary" strokeWidth={1.8} /></div>
					<div class="mt-6 flex min-h-[24rem] min-w-0 flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-border bg-muted/30 px-6 text-center sm:min-h-[34rem]">
						{#if audioUrl}
							<div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Music size={26} strokeWidth={1.7} /></div>
							<div class="min-w-0 max-w-full"><p class="break-words text-sm font-semibold" style="overflow-wrap:anywhere">{audioFilename}</p>{#if audioSizeBytes}<p class="mt-1 text-xs text-muted-foreground">{formatBytes(audioSizeBytes)}</p>{/if}</div>
							<audio class="w-full max-w-2xl" src={audioUrl} controls preload="metadata"><track kind="captions" /></audio>
							<OutlinedButton loading={downloading} disabled={downloading} onclick={() => void downloadMusic()}><Download size={16} strokeWidth={1.9} /><span>{downloading ? '음악 다운로드 중' : '음악 다운로드'}</span></OutlinedButton>
						{:else if generating}
							<LoadingSpinner size="lg" label="MiniMax-Music3 음악 생성 중" />
							<div><p class="text-sm font-medium">{statusLabel(status)}</p><p class="mt-1 text-xs text-muted-foreground">{Math.round(progress)}% · 경과 {formatElapsed(elapsedSeconds)}{#if queuePosition !== null} · 대기 {queuePosition}번째{/if}</p></div>
						{:else}
							<div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Music size={26} strokeWidth={1.7} /></div>
							{#if optionsLoading}<LoadingSpinner size="md" label="MiniMax-Music3 설정 확인 중" />{:else}<p class="text-sm font-medium">아직 생성된 음악이 없습니다.</p><p class="max-w-sm text-xs leading-5 text-muted-foreground">{serviceDetail}</p>{/if}
						{/if}
					</div>
					{#if generating && jobKey}<OutlinedButton class="mt-4 w-full" loading={cancelling} disabled={cancelling} onclick={() => void cancelGeneration()}><X size={16} strokeWidth={1.9} /><span>{cancelling ? '음악 생성 취소 중' : '음악 생성 취소'}</span></OutlinedButton>{/if}
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="music-settings-title">
					<div id="music-settings-title"><Typography as="h2" variant="h2">음악 생성 설정</Typography></div>
					<form class="mt-5 space-y-5 pb-24 sm:pb-0" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<div class="rounded-xl border border-border bg-muted/30 px-3 py-3"><span class="block text-xs font-medium text-muted-foreground">MODEL</span><span class="mt-1 block text-sm font-semibold text-foreground">{model}</span></div>
						<label class="block space-y-2" for="music-description"><span class="text-sm font-medium">음악 설명</span><textarea id="music-description" bind:value={description} rows="6" maxlength="5000" disabled={generating} class={textareaClass} placeholder="장르, 분위기, 보컬, 악기, 곡 전개를 설명해 주세요."></textarea><span class="block text-right text-xs text-muted-foreground">{description.length.toLocaleString('ko-KR')} / 5,000</span></label>
						<label class="block space-y-2" for="music-lyrics"><span class="text-sm font-medium">가사</span><textarea id="music-lyrics" bind:value={lyrics} rows="10" maxlength="5000" disabled={generating} class={textareaClass} placeholder={'[Verse]\n가사를 입력해 주세요.\n\n[Chorus]\n반복할 후렴을 입력해 주세요.'}></textarea><span class="block text-xs leading-5 text-muted-foreground">비워 두면 연주곡을 생성합니다. [Verse], [Chorus], [Bridge], [Instrumental] section tag를 줄 단위로 사용할 수 있습니다.</span><span class="block text-right text-xs text-muted-foreground">{lyrics.length.toLocaleString('ko-KR')} / 5,000</span></label>
						<div class="grid grid-cols-2 gap-3">
							<label class="block space-y-2" for="music-duration"><span class="text-sm font-medium">최대 길이</span><input id="music-duration" class={inputClass} type="number" min="10" max={maxDurationSeconds} step="1" bind:value={durationSeconds} disabled={generating} /><span class="block text-xs text-muted-foreground">초</span></label>
							<label class="block space-y-2" for="music-seed"><span class="text-sm font-medium">Seed</span><input id="music-seed" class={inputClass} type="number" min="0" max="9007199254740991" step="1" bind:value={seed} disabled={generating} placeholder="랜덤" /></label>
						</div>
						<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"><PrimaryButton type="submit" loading={generating} deactive={!serviceAvailable} disabled={!description.trim()} class="w-full"><Sparkles size={17} strokeWidth={1.9} /><span>{generating ? '음악 생성 중' : serviceAvailable ? '음악 생성' : 'MiniMax-Music3 연결 대기 중'}</span></PrimaryButton></div>
					</form>
				</section>
			</div>
		</div>
	</Layout>

	{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="음악 생성 오류" message={error} onclose={() => (error = '')} /></div>{/if}
	{#if notice}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="음악 생성" message={notice} onclose={() => (notice = '')} /></div>{/if}
{/if}
