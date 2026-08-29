<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Download, FileDown, Folder, RefreshCw, Trash2 } from '@lucide/svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';

	type ModelType = 'checkpoint' | 'lora' | 'text_encoder' | 'vae' | 'embedding';
	type FileInfo = {
		index: number;
		name: string;
		file_type: string;
		size_bytes: number | null;
		sha256: string | null;
		primary: boolean;
	};
	type Lookup = {
		version_id: number;
		model_id: number | null;
		model_name: string;
		model_type: string;
		version_name: string;
		base_model: string | null;
		files: FileInfo[];
		selected_file_index: number;
	};
	type DownloadJob = {
		id: string;
		version_id: number;
		model_type: ModelType;
		filename: string;
		status: 'queued' | 'downloading' | 'completed' | 'failed' | 'cancelled' | string;
		downloaded_bytes: number;
		total_bytes: number | null;
		error_message: string | null;
		created_at: string;
		completed_at: string | null;
	};
	type InstalledModel = {
		model_type: ModelType;
		filename: string;
		size_bytes: number;
		modified_at: string;
	};
	type ToastData = { state: 'positive' | 'negative' | 'info'; title: string; message: string };

	const modelTypes: { value: ModelType; label: string }[] = [
		{ value: 'checkpoint', label: '체크포인트' },
		{ value: 'lora', label: 'LoRA' },
		{ value: 'text_encoder', label: '텍스트 인코더' },
		{ value: 'vae', label: 'VAE' },
		{ value: 'embedding', label: '임베딩' }
	];
	const statusLabels: Record<string, string> = {
		queued: '대기 중',
		downloading: '다운로드 중',
		completed: '완료',
		failed: '실패',
		cancelled: '중단됨'
	};

	let ready = $state(false);
	let source = $state('');
	let modelType = $state<ModelType>('checkpoint');
	let lookup = $state<Lookup | null>(null);
	let selectedFileIndex = $state<number | null>(null);
	let lookupLoading = $state(false);
	let downloadLoading = $state(false);
	let jobs = $state<DownloadJob[]>([]);
	let installed = $state<InstalledModel[]>([]);
	let deleteTarget = $state<InstalledModel | null>(null);
	let deleteModalOpen = $state(false);
	let deleteLoading = $state<string | null>(null);
	let cancelLoadingId = $state('');
	let error = $state('');
	let toast = $state<ToastData | null>(null);
	let pollTimer: ReturnType<typeof setInterval> | undefined;

	onMount(() => {
		void initialize();
		return () => {
			if (pollTimer) clearInterval(pollTimer);
		};
	});

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			await refresh();
			pollTimer = setInterval(() => {
				if (jobs.some((job) => job.status === 'queued' || job.status === 'downloading')) void loadJobs();
			}, 2000);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '모델 정보를 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	async function refresh() {
		await Promise.all([loadJobs(), loadInstalled()]);
	}

	async function loadJobs() {
		jobs = await apiJson<DownloadJob[]>('models/downloads');
	}

	async function loadInstalled() {
		installed = await apiJson<InstalledModel[]>('models/installed');
	}

	async function lookupModel() {
		if (!source.trim()) {
			error = 'Civitai 모델 버전 ID 또는 링크를 입력해 주세요.';
			return;
		}
		lookupLoading = true;
		error = '';
		try {
			lookup = await apiJson<Lookup>(
				`models/civitai/lookup?source=${encodeURIComponent(source.trim())}&model_type=${modelType}`
			);
			selectedFileIndex = lookup.selected_file_index;
		} catch (reason) {
			lookup = null;
			error = reason instanceof Error ? reason.message : 'Civitai 모델 정보를 조회하지 못했습니다.';
		} finally {
			lookupLoading = false;
		}
	}

	async function startDownload() {
		if (!lookup || selectedFileIndex === null) return;
		downloadLoading = true;
		error = '';
		try {
			const job = await apiJson<DownloadJob>('models/civitai/download', {
				method: 'POST',
				json: { source: source.trim(), model_type: modelType, file_index: selectedFileIndex }
			});
			jobs = [job, ...jobs.filter((item) => item.id !== job.id)];
			lookup = null;
			showToast('positive', '다운로드 요청 완료', '모델 다운로드가 대기열에 추가되었습니다.');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '모델 다운로드를 요청하지 못했습니다.';
		} finally {
			downloadLoading = false;
		}
	}

	async function retryJob(downloadId: string) {
		error = '';
		try {
			const job = await apiJson<DownloadJob>(`models/downloads/${downloadId}/retry`, { method: 'POST' });
			jobs = jobs.map((item) => (item.id === job.id ? job : item));
			showToast('positive', '재시도 요청 완료', '모델 다운로드를 다시 시작했습니다.');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '다운로드를 다시 시도하지 못했습니다.';
		}
	}

	async function cancelJob(downloadId: string) {
		if (cancelLoadingId) return;
		cancelLoadingId = downloadId;
		error = '';
		try {
			const job = await apiJson<DownloadJob>(`models/downloads/${downloadId}/cancel`, { method: 'POST' });
			jobs = jobs.map((item) => (item.id === job.id ? job : item));
			showToast('positive', '다운로드 중단 완료', '다운로드를 중단하고 임시 파일을 삭제했습니다.');
		} catch (reason) {
			const message = reason instanceof Error ? reason.message : '다운로드를 중단하지 못했습니다.';
			error = message;
			showToast('negative', '다운로드 중단 실패', message);
		} finally {
			cancelLoadingId = '';
		}
	}

	function requestDeleteInstalledModel(model: InstalledModel) {
		if (deleteLoading !== null) return;
		deleteTarget = model;
		deleteModalOpen = true;
	}

	function cancelDelete() {
		if (deleteLoading !== null) return;
		deleteModalOpen = false;
		deleteTarget = null;
	}

	async function deleteInstalledModel() {
		const model = deleteTarget;
		if (!model) return;
		const key = `${model.model_type}:${model.filename}`;
		deleteLoading = key;
		error = '';
		try {
			const encodedFilename = model.filename.split('/').map(encodeURIComponent).join('/');
			await apiDelete(`models/installed/${encodeURIComponent(model.model_type)}/${encodedFilename}`);
			installed = installed.filter((item) => `${item.model_type}:${item.filename}` !== key);
			deleteModalOpen = false;
			deleteTarget = null;
			showToast('positive', '모델 삭제 완료', `${model.filename}을(를) 삭제했습니다.`);
		} catch (reason) {
			const message = reason instanceof Error ? reason.message : '모델을 삭제하지 못했습니다.';
			error = message;
			showToast('negative', '모델 삭제 실패', message);
		} finally {
			deleteLoading = null;
		}
	}

	function chooseType(value: ModelType) {
		modelType = value;
		lookup = null;
		selectedFileIndex = null;
	}

	function showToast(state: ToastData['state'], title: string, message: string) {
		toast = { state, title, message };
	}

	function formatSize(bytes: number | null) {
		if (bytes === null || bytes === 0) return '크기 확인 불가';
		const units = ['B', 'KB', 'MB', 'GB', 'TB'];
		let value = bytes;
		let unit = 0;
		while (value >= 1024 && unit < units.length - 1) {
			value /= 1024;
			unit += 1;
		}
		return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
	}

	function progress(job: DownloadJob) {
		if (!job.total_bytes) return null;
		return Math.min(100, Math.round((job.downloaded_bytes / job.total_bytes) * 100));
	}

	function typeLabel(value: ModelType) {
		return modelTypes.find((item) => item.value === value)?.label ?? value;
	}
</script>

<svelte:head>
	<title>civitai 다운로드 · Local Field</title>
	<meta name="description" content="Civitai 모델을 ComfyUI 모델 폴더에 다운로드합니다." />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="civitai 다운로드를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<div>
					<Typography as="h1" variant="display">civitai 다운로드</Typography>
				</div>
				<OutlinedButton class="gap-2" onclick={() => void refresh()}><RefreshCw size={16} />새로고침</OutlinedButton>
			</div>

			<section class="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
				<div class="flex flex-wrap gap-2" role="tablist" aria-label="모델 종류">
					{#each modelTypes as item}
						<button type="button" role="tab" aria-selected={modelType === item.value} onclick={() => chooseType(item.value)} class={`rounded-lg border px-3 py-2 text-sm font-semibold transition ${modelType === item.value ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'}`}>{item.label}</button>
					{/each}
				</div>
				<form class="flex flex-col gap-3 md:flex-row" onsubmit={(event) => { event.preventDefault(); void lookupModel(); }}>
					<label class="sr-only" for="civitai-source">Civitai 모델 버전 ID 또는 링크</label>
					<input id="civitai-source" bind:value={source} placeholder="Civitai 모델 버전 ID 또는 링크" class="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring" />
					<button type="submit" disabled={lookupLoading} class="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">{#if lookupLoading}<LoadingSpinner size="sm" label="조회 중" />{:else}<Download size={16} />모델 조회{/if}</button>
				</form>
			</section>

			{#if lookup}
				<section class="space-y-4 rounded-2xl border border-primary/30 bg-primary/5 p-5">
					<div><p class="text-lg font-semibold">{lookup.model_name}</p><p class="mt-1 text-sm text-muted-foreground">{lookup.version_name}{#if lookup.base_model} · {lookup.base_model}{/if}</p></div>
					<div class="space-y-2">
						<p class="text-sm font-semibold">다운로드할 파일</p>
						{#each lookup.files as file}
							<button type="button" onclick={() => (selectedFileIndex = file.index)} class={`flex w-full items-center justify-between gap-3 rounded-lg border p-3 text-left transition ${selectedFileIndex === file.index ? 'border-primary bg-background ring-1 ring-primary' : 'border-border bg-background/60 hover:bg-background'}`}>
								<span class="min-w-0"><span class="block truncate text-sm font-medium">{file.name}</span><span class="mt-1 block text-xs text-muted-foreground">{file.file_type} · {formatSize(file.size_bytes)}{#if file.primary} · 기본 파일{/if}</span></span>
								<span class="shrink-0 text-xs text-muted-foreground">{selectedFileIndex === file.index ? '선택됨' : '선택'}</span>
							</button>
						{/each}
					</div>
					<div class="flex justify-end"><button type="button" disabled={downloadLoading || selectedFileIndex === null} onclick={() => void startDownload()} class="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">{#if downloadLoading}<LoadingSpinner size="sm" label="요청 중" />{:else}<FileDown size={16} />다운로드 시작{/if}</button></div>
				</section>
			{/if}

			{#if error}<div class="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">{error}</div>{/if}

			<section class="space-y-3">
				<div class="flex items-center justify-between"><Typography as="h2" variant="h2">다운로드 상태</Typography></div>
				{#if jobs.length === 0}<div class="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">요청한 모델 다운로드가 없습니다.</div>
				{:else}<div class="space-y-3">{#each jobs as job (job.id)}<article class="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm"><div class="flex flex-wrap items-start justify-between gap-3"><div class="min-w-0"><p class="truncate text-sm font-semibold" title={job.filename}>{job.filename}</p><p class="mt-1 text-xs text-muted-foreground">{typeLabel(job.model_type)} · version {job.version_id}</p></div><span class={`rounded-full px-2.5 py-1 text-xs font-semibold ${job.status === 'completed' ? 'bg-success/10 text-success' : job.status === 'failed' ? 'bg-destructive/10 text-destructive' : job.status === 'cancelled' ? 'bg-muted text-muted-foreground' : 'bg-primary/10 text-primary'}`}>{statusLabels[job.status] ?? job.status}</span></div>{#if job.status === 'queued' || job.status === 'downloading'}<div class="flex items-center gap-3"><div class="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-muted"><div class="h-full rounded-full bg-primary transition-all" style={`width: ${progress(job) ?? 0}%`}></div></div><button type="button" disabled={cancelLoadingId !== ''} onclick={() => void cancelJob(job.id)} class="shrink-0 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50">{#if cancelLoadingId === job.id}<LoadingSpinner size="sm" label="중단 중" />{:else}중단{/if}</button></div><p class="text-xs text-muted-foreground">{formatSize(job.downloaded_bytes)}{#if job.total_bytes} / {formatSize(job.total_bytes)} · {progress(job)}%{/if}</p>{:else if job.status === 'failed' || job.status === 'cancelled'}<div class="flex flex-wrap items-center justify-between gap-3"><p class={`text-xs ${job.status === 'cancelled' ? 'text-muted-foreground' : 'text-destructive'}`}>{job.status === 'cancelled' ? '다운로드가 중단되었습니다. 임시 파일은 삭제되었습니다.' : job.error_message ?? '다운로드에 실패했습니다.'}</p><button type="button" class="rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted" onclick={() => void retryJob(job.id)}>다시 시도</button></div>{:else}<p class="text-xs text-success">{formatSize(job.total_bytes ?? job.downloaded_bytes)} · ComfyUI 모델 폴더에 저장됨</p>{/if}</article>{/each}</div>{/if}
			</section>

			<section class="space-y-3">
				<div class="flex items-center justify-between"><Typography as="h2" variant="h2">설치된 모델</Typography><span class="text-xs text-muted-foreground">{installed.length}개</span></div>
				{#if installed.length === 0}<div class="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">ComfyUI 모델 폴더에 설치된 모델이 없습니다.</div>
				{:else}<div class="grid gap-3 md:grid-cols-2">{#each installed as model}<article class="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-card p-3"><Folder size={18} class="shrink-0 text-primary" /><div class="min-w-0 flex-1"><p class="truncate text-sm font-medium" title={model.filename}>{model.filename}</p><p class="mt-1 text-xs text-muted-foreground">{typeLabel(model.model_type)} · {formatSize(model.size_bytes)}</p></div><button type="button" aria-label={`${model.filename} 삭제`} title="삭제" disabled={deleteLoading !== null} onclick={() => requestDeleteInstalledModel(model)} class="inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-50">{#if deleteLoading === `${model.model_type}:${model.filename}`}<LoadingSpinner size="sm" label="삭제 중" />{:else}<Trash2 size={16} />{/if}</button></article>{/each}</div>{/if}
			</section>
		</div>
	</Layout>
	{#if toast}<div class="fixed right-4 top-4 z-50"><Toast state={toast.state} title={toast.title} message={toast.message} onclose={() => (toast = null)} /></div>{/if}
{/if}

{#if deleteTarget}
	<Modal bind:open={deleteModalOpen} title="설치된 모델을 삭제하시겠습니까?" description="삭제한 모델 파일은 복구할 수 없습니다." closeOnBackdrop={!deleteLoading} onclose={cancelDelete}>
		<p class="text-sm leading-6 text-muted-foreground"><strong class="font-semibold text-foreground">{deleteTarget.filename}</strong> 파일을 ComfyUI 모델 폴더에서 삭제합니다.</p>
		{#snippet footer()}
			<OutlinedButton disabled={deleteLoading !== null} onclick={cancelDelete}>취소</OutlinedButton>
			<PrimaryButton loading={deleteLoading !== null} variant="destructive" onclick={() => void deleteInstalledModel()}>
				<Trash2 size={16} strokeWidth={2} />
				<span>삭제</span>
			</PrimaryButton>
		{/snippet}
	</Modal>
{/if}
