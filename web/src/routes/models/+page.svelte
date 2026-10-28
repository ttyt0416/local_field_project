<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Download, FileDown, RefreshCw } from '@lucide/svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiJson } from '$lib/utils/api';
	import ModelFolderPicker from '../../../components/models/model-folder-picker.svelte';
	import { modelTypes, type ModelType } from '$lib/types/model-storage';
	import type { DownloadJob, DownloadProvider } from '$lib/types/model-downloads';
	import Tab from '../../../components/tabs/tab.svelte';
	import HuggingFaceDownload from '../../../components/downloads/hugging-face-download.svelte';
	import DownloadToken from '../../../components/downloads/download-token.svelte';

	type FileInfo = {
		index: number;
		name: string;
		file_type: string;
		size_bytes: number | null;
		sha256: string | null;
		primary: boolean;
	};
	type VersionOption = {
		version_id: number;
		version_name: string;
		base_model: string | null;
		published_at: string | null;
	};
	type Lookup = {
		version_id: number;
		model_id: number | null;
		model_name: string;
		model_type: string;
		version_name: string;
		base_model: string | null;
		target_model_type: ModelType;
		suggested_subfolder: string;
		files: FileInfo[];
		selected_file_index: number;
		versions: VersionOption[];
	};
	type ToastData = { state: 'positive' | 'negative' | 'info'; title: string; message: string };

	const statusLabels: Record<string, string> = {
		queued: '대기 중',
		downloading: '다운로드 중'
	};

	let ready = $state(false);
	let provider = $state<DownloadProvider>('civitai');
	let huggingFaceBusy = $state(false);
	let lookupRequest = 0;
	let jobsRevision = 0;
	let source = $state('');
	let modelType = $state<ModelType>('checkpoint');
	let modelTypeOverridden = $state(false);
	let subfolder = $state('');
	let lookup = $state<Lookup | null>(null);
	let versionOptions = $state<VersionOption[]>([]);
	let versionModalOpen = $state(false);
	let versionLoadingId = $state<number | null>(null);
	let selectedFileIndex = $state<number | null>(null);
	let lookupLoading = $state(false);
	let downloadLoading = $state(false);
	let jobs = $state<DownloadJob[]>([]);
	let folderModalOpen = $state(false);
	let refreshing = $state(false);
	let jobsLoading = false;
	let cancelLoadingId = $state('');
	let error = $state('');
	let toast = $state<ToastData | null>(null);
	let pollTimer: ReturnType<typeof setInterval> | undefined;
	let active = true;
	let providerTabs = $derived([
		{ value: 'civitai' as const, label: 'Civitai', disabled: downloadLoading || lookupLoading || versionLoadingId !== null || huggingFaceBusy },
		{ value: 'hugging_face' as const, label: 'Hugging Face', disabled: downloadLoading || lookupLoading || versionLoadingId !== null || huggingFaceBusy }
	]);

	onMount(() => {
		void initialize();
		return () => {
			active = false;
			if (pollTimer) clearInterval(pollTimer);
		};
	});

	async function initialize() {
		await authStore.initialize();
		if (!active) return;
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			await refresh();
			if (!active) return;
			pollTimer = setInterval(() => {
				if (jobs.length > 0) void loadJobs();
			}, 2000);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '모델 정보를 불러오지 못했습니다.';
			showToast('negative', '모델 정보 조회 실패', error);
		} finally {
			ready = true;
		}
	}

	async function refresh() {
		if (refreshing) return;
		refreshing = true;
		try {
			await loadJobs();
		} finally {
			refreshing = false;
		}
	}

	async function loadJobs() {
		if (jobsLoading) return;
		jobsLoading = true;
		const revision = jobsRevision;
		try {
			const result = await apiJson<DownloadJob[]>('models/downloads?limit=100');
			if (active && revision === jobsRevision) {
				const failed = result.find((job) => job.status === 'failed' && jobs.some((previous) => previous.id === job.id));
				if (failed) {
					error = `${failed.filename}: ${failed.error_message ?? '모델 다운로드에 실패했습니다.'}`;
					showToast('negative', '다운로드 실패', error);
				}
				jobs = result.filter((job) => job.status === 'queued' || job.status === 'downloading');
			}
		} catch (reason) {
			if (!active) return;
			error = reason instanceof Error ? reason.message : '다운로드 목록을 불러오지 못했습니다.';
			showToast('negative', '다운로드 목록 조회 실패', error);
		} finally {
			jobsLoading = false;
		}
	}

	async function lookupModel() {
		const requestedSource = source.trim();
		const requestedType = modelType;
		if (!requestedSource) {
			error = 'Civitai 모델 링크, 버전 ID 또는 버전 링크를 입력해 주세요.';
			return;
		}
		const request = ++lookupRequest;
		lookupLoading = true;
		error = '';
		try {
			const result = await apiJson<Lookup>(
				`models/civitai/lookup?source=${encodeURIComponent(requestedSource)}&model_type=${requestedType}`
			);
			if (!active || request !== lookupRequest || provider !== 'civitai' || source.trim() !== requestedSource || modelType !== requestedType) return;
			applyLookup(result);
		} catch (reason) {
			if (!active || request !== lookupRequest) return;
			lookup = null;
			error = reason instanceof Error ? reason.message : 'Civitai 모델 정보를 조회하지 못했습니다.';
			showToast('negative', '모델 조회 실패', error);
		} finally {
			if (active && request === lookupRequest) lookupLoading = false;
		}
	}

	function applyLookup(result: Lookup, preserveOverride = false) {
		if (!preserveOverride || !modelTypeOverridden) {
			modelType = result.target_model_type;
			modelTypeOverridden = false;
		}
		lookup = result;
		versionOptions = result.versions;
		selectedFileIndex = result.selected_file_index;
		subfolder = modelType === result.target_model_type ? result.suggested_subfolder : '';
	}

	function clearLookupSelection() {
		modelTypeOverridden = false;
		lookupRequest += 1;
		lookupLoading = false;
		versionLoadingId = null;
		folderModalOpen = false;
		lookup = null;
		versionOptions = [];
		versionModalOpen = false;
		selectedFileIndex = null;
		subfolder = '';
	}

	async function selectVersion(versionId: number) {
		if (!lookup || versionLoadingId !== null) return;
		if (versionId === lookup.version_id) {
			versionModalOpen = false;
			return;
		}
		const requestedType = modelType;
		const request = ++lookupRequest;
		versionLoadingId = versionId;
		error = '';
		try {
			const result = await apiJson<Lookup>(
				`models/civitai/lookup?source=${versionId}&model_type=${requestedType}`
			);
			if (!active || request !== lookupRequest || provider !== 'civitai' || modelType !== requestedType) return;
			applyLookup(result, true);
			versionModalOpen = false;
		} catch (reason) {
			if (!active || request !== lookupRequest) return;
			const message = reason instanceof Error ? reason.message : '모델 버전을 불러오지 못했습니다.';
			error = message;
			showToast('negative', '모델 버전 선택 실패', message);
		} finally {
			if (active && request === lookupRequest) versionLoadingId = null;
		}
	}

	async function startDownload(folder: string) {
		if (!lookup || selectedFileIndex === null || downloadLoading) return;
		downloadLoading = true;
		error = '';
		try {
			const job = await apiJson<DownloadJob>('models/civitai/download', {
				method: 'POST',
				json: { source: String(lookup.version_id), model_type: modelType, file_index: selectedFileIndex, subfolder: folder }
			});
			if (!active) return;
			addDownloadJob(job);
			lookup = null;
			versionOptions = [];
			source = '';
			selectedFileIndex = null;
			subfolder = '';
			folderModalOpen = false;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '모델 다운로드를 요청하지 못했습니다.';
			showToast('negative', '다운로드 요청 실패', error);
		} finally {
			downloadLoading = false;
		}
	}

	function openFolderModal() {
		if (!lookup || selectedFileIndex === null) return;
		folderModalOpen = true;
	}

	async function cancelJob(downloadId: string) {
		if (cancelLoadingId) return;
		cancelLoadingId = downloadId;
		error = '';
		try {
			await apiJson<DownloadJob>(`models/downloads/${downloadId}/cancel`, { method: 'POST' });
			jobsRevision += 1;
			jobs = jobs.filter((item) => item.id !== downloadId);
			showToast('positive', '다운로드 중단 완료', '다운로드를 중단하고 임시 파일을 삭제했습니다.');
		} catch (reason) {
			const message = reason instanceof Error ? reason.message : '다운로드를 중단하지 못했습니다.';
			error = message;
			showToast('negative', '다운로드 중단 실패', message);
		} finally {
			cancelLoadingId = '';
		}
	}

	function chooseType(value: ModelType) {
		if (downloadLoading || lookupLoading || versionLoadingId !== null || value === modelType) return;
		modelType = value;
		modelTypeOverridden = true;
		subfolder = lookup?.target_model_type === value ? lookup.suggested_subfolder : '';
	}

	function chooseProvider(value: DownloadProvider) {
		if (downloadLoading || lookupLoading || versionLoadingId !== null || huggingFaceBusy) return false;
		provider = value;
		source = '';
		error = '';
		clearLookupSelection();
	}

	function addDownloadJob(job: DownloadJob) {
		jobsRevision += 1;
		jobs = [job, ...jobs.filter((item) => item.id !== job.id)];
		showToast('positive', '다운로드 요청 완료', '모델 다운로드가 대기열에 추가되었습니다.');
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

	function formatDate(value: string | null) {
		return value ? new Date(value).toLocaleDateString('ko-KR') : '날짜 정보 없음';
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
	<title>다운로드 관리 · Local Field</title>
	<meta name="description" content="Civitai와 Hugging Face 모델 다운로드를 관리합니다." />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="다운로드 관리를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<div>
					<Typography as="h1" variant="display">다운로드 관리</Typography>
					<p class="mt-2 text-sm text-muted-foreground">모델을 찾아 다운로드하세요. 저장된 파일은 <a href="/files" class="font-medium text-primary hover:underline">파일 관리</a>에서 정리할 수 있습니다.</p>
				</div>
				<OutlinedButton class="gap-2" loading={refreshing} onclick={() => void refresh()}><RefreshCw size={16} />새로고침</OutlinedButton>
			</div>

			<Tab items={providerTabs} value={provider} onselect={chooseProvider} ariaLabel="다운로드 출처" />
			<DownloadToken {provider} />

			{#if provider === 'civitai'}
			<section class="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
				<div class="flex flex-wrap gap-2" role="tablist" aria-label="모델 종류">
					{#each modelTypes as item}
						<button type="button" role="tab" disabled={downloadLoading || lookupLoading || versionLoadingId !== null} aria-selected={modelType === item.value} onclick={() => chooseType(item.value)} class={`rounded-lg border px-3 py-2 text-sm font-semibold transition disabled:opacity-50 ${modelType === item.value ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'}`}>{item.label}</button>
					{/each}
				</div>
				<form class="flex flex-col gap-3 md:flex-row" onsubmit={(event) => { event.preventDefault(); void lookupModel(); }}>
					<label class="sr-only" for="civitai-source">Civitai 모델 링크, 버전 ID 또는 버전 링크</label>
					<input id="civitai-source" bind:value={source} oninput={clearLookupSelection} placeholder="Civitai 모델 링크, 버전 ID 또는 버전 링크" class="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring" />
					<button type="submit" disabled={lookupLoading} class="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">{#if lookupLoading}<LoadingSpinner size="sm" label="조회 중" />{:else}<Download size={16} />모델 조회{/if}</button>
				</form>
			</section>

			{#if lookup}
				<section class="space-y-4 rounded-2xl border border-primary/30 bg-primary/5 p-5">
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div><p class="text-lg font-semibold">{lookup.model_name}</p><p class="mt-1 text-sm text-muted-foreground">{lookup.version_name}{#if lookup.base_model} · {lookup.base_model}{/if}</p><p class="mt-1 text-xs text-primary">저장 종류: {typeLabel(modelType)} / {subfolder || '전체'}</p><p class="mt-1 text-xs text-muted-foreground">자동 선택된 모델 종류는 위에서 변경할 수 있습니다.</p></div>
						{#if versionOptions.length > 1}<OutlinedButton disabled={versionLoadingId !== null} onclick={() => (versionModalOpen = true)}>버전 선택</OutlinedButton>{/if}
					</div>
					<div class="space-y-2">
						<p class="text-sm font-semibold">다운로드할 파일</p>
						{#each lookup.files as file}
							<button type="button" onclick={() => (selectedFileIndex = file.index)} class={`flex w-full items-center justify-between gap-3 rounded-lg border p-3 text-left transition ${selectedFileIndex === file.index ? 'border-primary bg-background ring-1 ring-primary' : 'border-border bg-background/60 hover:bg-background'}`}>
								<span class="min-w-0"><span class="block truncate text-sm font-medium">{file.name}</span><span class="mt-1 block text-xs text-muted-foreground">{file.file_type} · {formatSize(file.size_bytes)}{#if file.primary} · 기본 파일{/if}</span></span>
								<span class="shrink-0 text-xs text-muted-foreground">{selectedFileIndex === file.index ? '선택됨' : '선택'}</span>
							</button>
						{/each}
					</div>
					<div class="flex justify-end"><button type="button" disabled={downloadLoading || selectedFileIndex === null} onclick={() => void openFolderModal()} class="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"><FileDown size={16} />다운로드</button></div>
				</section>
			{/if}


			{:else}
				<HuggingFaceDownload bind:busy={huggingFaceBusy} ondownload={addDownloadJob} />
			{/if}

			{#if error}<div class="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">{error}</div>{/if}

			<section class="space-y-3">
				<div class="flex items-center justify-between"><Typography as="h2" variant="h2">다운로드 중인 콘텐츠</Typography></div>
				{#if jobs.length === 0}<div class="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">다운로드 중인 콘텐츠가 없습니다.</div>
								{:else}
									<div class="space-y-3">
										{#each jobs as job (job.id)}
											<article class="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm">
												<div class="flex flex-wrap items-start justify-between gap-3">
													<div class="min-w-0"><p class="truncate text-sm font-semibold" title={`${job.subfolder ? `${job.subfolder}/` : ''}${job.filename}`}>{job.subfolder ? `${job.subfolder}/` : ''}{job.filename}</p><p class="mt-1 text-xs text-muted-foreground">{job.provider === 'hugging_face' ? 'Hugging Face' : 'Civitai'} · {typeLabel(job.model_type)}{#if job.provider === 'hugging_face'} · {job.source_repo} · {job.source_revision?.slice(0, 12)}{:else} · version {job.version_id}{/if}</p></div>
													<span class="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">{statusLabels[job.status] ?? job.status}</span>
												</div>
												<div class="flex items-center gap-3"><div class="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-muted"><div class="h-full rounded-full bg-primary transition-all" style={`width: ${progress(job) ?? 0}%`}></div></div><button type="button" disabled={cancelLoadingId !== ''} onclick={() => void cancelJob(job.id)} class="shrink-0 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50">{#if cancelLoadingId === job.id}<LoadingSpinner size="sm" label="중단 중" />{:else}중단{/if}</button></div>
												<p class="text-xs text-muted-foreground">{formatSize(job.downloaded_bytes)}{#if job.total_bytes} / {formatSize(job.total_bytes)} · {progress(job)}%{/if}</p>
											</article>
										{/each}
									</div>
								{/if}
			</section>

		</div>
	</Layout>
	{#if toast}<div class="fixed right-4 top-4 z-50"><Toast state={toast.state} title={toast.title} message={toast.message} onclose={() => (toast = null)} /></div>{/if}
{/if}

<Modal bind:open={versionModalOpen} title="모델 버전 선택" description="최신 호환 버전이 기본으로 선택됩니다. 다른 버전을 선택하면 파일 목록도 함께 바뀝니다." closeOnBackdrop={versionLoadingId === null}>
	<div class="grid max-h-[55dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
		{#each versionOptions as version (version.version_id)}
			<button
				type="button"
				disabled={versionLoadingId !== null}
				onclick={() => void selectVersion(version.version_id)}
				class={`min-w-0 rounded-xl border p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${lookup?.version_id === version.version_id ? 'border-primary bg-primary/10 ring-1 ring-primary' : 'border-border hover:bg-muted'}`}
			>
				<span class="flex items-start justify-between gap-2"><span class="text-sm font-semibold leading-5">{version.version_name}</span>{#if versionLoadingId === version.version_id}<LoadingSpinner size="sm" label="버전 불러오는 중" />{:else if lookup?.version_id === version.version_id}<span class="shrink-0 text-xs text-primary">선택됨</span>{/if}</span>
				<span class="mt-1 block text-xs leading-5 text-muted-foreground">{version.base_model ?? 'Base model 정보 없음'} · {formatDate(version.published_at)}</span>
			</button>
		{/each}
	</div>
	{#snippet footer()}
		<OutlinedButton disabled={versionLoadingId !== null} onclick={() => (versionModalOpen = false)}>닫기</OutlinedButton>
	{/snippet}
</Modal>

<ModelFolderPicker
	bind:open={folderModalOpen}
	{modelType}
	onmodeltypechange={chooseType}
	initialFolder={subfolder}
	title="저장 폴더 선택"
	confirmLabel="선택한 폴더에 다운로드"
	loading={downloadLoading}
	onconfirm={(folder) => void startDownload(folder)}
/>
