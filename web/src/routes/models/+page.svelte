<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Download, FileDown, Folder, Plus, RefreshCw, Trash2 } from '@lucide/svelte';
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
		files: FileInfo[];
		selected_file_index: number;
		versions: VersionOption[];
	};
	type DownloadJob = {
		id: string;
		version_id: number;
		model_type: ModelType;
		subfolder: string;
		filename: string;
		status: 'queued' | 'downloading';
		downloaded_bytes: number;
		total_bytes: number | null;
		created_at: string;
	};
	type InstalledModel = {
		model_type: ModelType;
		filename: string;
		size_bytes: number;
		modified_at: string;
	};
	type ModelFolder = { model_type: ModelType; subfolder: string };
	type ToastData = { state: 'positive' | 'negative' | 'info'; title: string; message: string };

	const modelTypes: { value: ModelType; label: string }[] = [
		{ value: 'checkpoint', label: '체크포인트' },
		{ value: 'lora', label: 'LoRA' },
		{ value: 'text_encoder', label: '텍스트 인코더' },
		{ value: 'vae', label: 'VAE' },
		{ value: 'embedding', label: '임베딩' }
	];
	const modelFolders: Record<ModelType, string> = {
		checkpoint: 'diffusion_models',
		lora: 'loras',
		text_encoder: 'text_encoders',
		vae: 'vae',
		embedding: 'embeddings'
	};
	const statusLabels: Record<string, string> = {
		queued: '대기 중',
		downloading: '다운로드 중'
	};

	let ready = $state(false);
	let source = $state('');
	let modelType = $state<ModelType>('checkpoint');
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
	let folders = $state<ModelFolder[]>([]);
	let foldersLoading = $state(false);
	let creatingFolder = $state(false);
	let folderCreating = $state(false);
	let newFolderName = $state('');
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
				if (jobs.length > 0) void loadJobs();
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
		jobs = await apiJson<DownloadJob[]>('models/downloads?active_only=true');
	}

	async function loadInstalled() {
		installed = await apiJson<InstalledModel[]>('models/installed');
	}

	async function lookupModel() {
		const requestedSource = source.trim();
		const requestedType = modelType;
		if (!requestedSource) {
			error = 'Civitai 모델 링크, 버전 ID 또는 버전 링크를 입력해 주세요.';
			return;
		}
		lookupLoading = true;
		error = '';
		try {
			const result = await apiJson<Lookup>(
				`models/civitai/lookup?source=${encodeURIComponent(requestedSource)}&model_type=${requestedType}`
			);
			if (source.trim() !== requestedSource || modelType !== requestedType) return;
			lookup = result;
			versionOptions = result.versions;
			selectedFileIndex = result.selected_file_index;
		} catch (reason) {
			lookup = null;
			error = reason instanceof Error ? reason.message : 'Civitai 모델 정보를 조회하지 못했습니다.';
		} finally {
			lookupLoading = false;
		}
	}

	function clearLookupSelection() {
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
		versionLoadingId = versionId;
		error = '';
		try {
			const result = await apiJson<Lookup>(
				`models/civitai/lookup?source=${versionId}&model_type=${requestedType}`
			);
			if (modelType !== requestedType) return;
			lookup = result;
			selectedFileIndex = result.selected_file_index;
			versionModalOpen = false;
		} catch (reason) {
			const message = reason instanceof Error ? reason.message : '모델 버전을 불러오지 못했습니다.';
			error = message;
			showToast('negative', '모델 버전 선택 실패', message);
		} finally {
			versionLoadingId = null;
		}
	}

	async function startDownload() {
		if (!lookup || selectedFileIndex === null) return;
		downloadLoading = true;
		error = '';
		try {
			const job = await apiJson<DownloadJob>('models/civitai/download', {
				method: 'POST',
				json: { source: String(lookup.version_id), model_type: modelType, file_index: selectedFileIndex, subfolder: subfolder.trim() }
			});
			jobs = [job, ...jobs.filter((item) => item.id !== job.id)];
			lookup = null;
			versionOptions = [];
			source = '';
			selectedFileIndex = null;
			subfolder = '';
			folderModalOpen = false;
			showToast('positive', '다운로드 요청 완료', '모델 다운로드가 대기열에 추가되었습니다.');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '모델 다운로드를 요청하지 못했습니다.';
		} finally {
			downloadLoading = false;
		}
	}

	async function openFolderModal() {
		if (!lookup || selectedFileIndex === null) return;
		folderModalOpen = true;
		creatingFolder = false;
		newFolderName = '';
		foldersLoading = true;
		error = '';
		try {
			folders = await apiJson<ModelFolder[]>(`models/folders?model_type=${modelType}`);
			if (!folders.some((folder) => folder.subfolder === subfolder)) subfolder = '';
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '모델 폴더를 불러오지 못했습니다.';
			folderModalOpen = false;
		} finally {
			foldersLoading = false;
		}
	}

	async function createFolder() {
		if (!newFolderName.trim() || folderCreating) return;
		folderCreating = true;
		error = '';
		try {
			const folder = await apiJson<ModelFolder>('models/folders', {
				method: 'POST',
				json: { model_type: modelType, parent: subfolder, name: newFolderName.trim() }
			});
			folders = [...folders.filter((item) => item.subfolder !== folder.subfolder), folder].sort((a, b) => a.subfolder.localeCompare(b.subfolder));
			subfolder = folder.subfolder;
			creatingFolder = false;
			newFolderName = '';
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '새 모델 폴더를 만들지 못했습니다.';
		} finally {
			folderCreating = false;
		}
	}

	async function cancelJob(downloadId: string) {
		if (cancelLoadingId) return;
		cancelLoadingId = downloadId;
		error = '';
		try {
			await apiJson<DownloadJob>(`models/downloads/${downloadId}/cancel`, { method: 'POST' });
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
		versionOptions = [];
		versionModalOpen = false;
		selectedFileIndex = null;
		folderModalOpen = false;
		subfolder = '';
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
	<title>CIVITAI 다운로드 · Local Field</title>
	<meta name="description" content="Civitai 모델을 ComfyUI 모델 폴더에 다운로드합니다." />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="CIVITAI 다운로드를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<div>
					<Typography as="h1" variant="display">CIVITAI 다운로드</Typography>
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
					<label class="sr-only" for="civitai-source">Civitai 모델 링크, 버전 ID 또는 버전 링크</label>
					<input id="civitai-source" bind:value={source} oninput={clearLookupSelection} placeholder="Civitai 모델 링크, 버전 ID 또는 버전 링크" class="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring" />
					<button type="submit" disabled={lookupLoading} class="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">{#if lookupLoading}<LoadingSpinner size="sm" label="조회 중" />{:else}<Download size={16} />모델 조회{/if}</button>
				</form>
			</section>

			{#if lookup}
				<section class="space-y-4 rounded-2xl border border-primary/30 bg-primary/5 p-5">
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div><p class="text-lg font-semibold">{lookup.model_name}</p><p class="mt-1 text-sm text-muted-foreground">{lookup.version_name}{#if lookup.base_model} · {lookup.base_model}{/if}</p></div>
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

			{#if error}<div class="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">{error}</div>{/if}

			<section class="space-y-3">
				<div class="flex items-center justify-between"><Typography as="h2" variant="h2">다운로드 중인 콘텐츠</Typography></div>
				{#if jobs.length === 0}<div class="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">다운로드 중인 콘텐츠가 없습니다.</div>
								{:else}
									<div class="space-y-3">
										{#each jobs as job (job.id)}
											<article class="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm">
												<div class="flex flex-wrap items-start justify-between gap-3">
													<div class="min-w-0"><p class="truncate text-sm font-semibold" title={`${job.subfolder ? `${job.subfolder}/` : ''}${job.filename}`}>{job.subfolder ? `${job.subfolder}/` : ''}{job.filename}</p><p class="mt-1 text-xs text-muted-foreground">{typeLabel(job.model_type)} · version {job.version_id}</p></div>
													<span class="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">{statusLabels[job.status] ?? job.status}</span>
												</div>
												<div class="flex items-center gap-3"><div class="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-muted"><div class="h-full rounded-full bg-primary transition-all" style={`width: ${progress(job) ?? 0}%`}></div></div><button type="button" disabled={cancelLoadingId !== ''} onclick={() => void cancelJob(job.id)} class="shrink-0 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50">{#if cancelLoadingId === job.id}<LoadingSpinner size="sm" label="중단 중" />{:else}중단{/if}</button></div>
												<p class="text-xs text-muted-foreground">{formatSize(job.downloaded_bytes)}{#if job.total_bytes} / {formatSize(job.total_bytes)} · {progress(job)}%{/if}</p>
											</article>
										{/each}
									</div>
								{/if}
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

<Modal bind:open={folderModalOpen} title="저장 폴더 선택" description={`${modelFolders[modelType]} 아래의 기존 폴더를 선택하거나 새 폴더를 만드세요.`} closeOnBackdrop={!downloadLoading && !folderCreating}>
	{#if foldersLoading}
		<div class="flex min-h-40 items-center justify-center"><LoadingSpinner size="lg" label="폴더를 불러오는 중" /></div>
	{:else}
		<div class="space-y-4">
			<div class="grid max-h-[50dvh] grid-cols-2 gap-2 overflow-y-auto pr-1">
				{#each folders as folder (folder.subfolder)}
					<button type="button" onclick={() => (subfolder = folder.subfolder)} class={`flex min-w-0 items-center gap-2 rounded-xl border p-3 text-left transition ${subfolder === folder.subfolder ? 'border-primary bg-primary/10 ring-1 ring-primary' : 'border-border hover:bg-muted'}`}>
						<Folder size={17} class="shrink-0 text-primary" />
						<span class="truncate text-sm font-medium" title={folder.subfolder || '기본 폴더'}>{folder.subfolder || '기본 폴더'}</span>
					</button>
				{/each}
			</div>
			{#if creatingFolder}
				<form class="space-y-3 rounded-xl border border-border bg-muted/30 p-3" onsubmit={(event) => { event.preventDefault(); void createFolder(); }}>
					<label class="block space-y-2" for="new-model-folder"><span class="text-sm font-semibold">{subfolder ? `${subfolder} 아래 새 폴더 이름` : '새 폴더 이름'}</span><input id="new-model-folder" bind:value={newFolderName} maxlength="120" placeholder="예: anime" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /></label>
					<div class="flex justify-end gap-2"><OutlinedButton disabled={folderCreating} onclick={() => (creatingFolder = false)}>취소</OutlinedButton><PrimaryButton type="submit" loading={folderCreating} disabled={!newFolderName.trim()}>폴더 추가</PrimaryButton></div>
				</form>
			{:else}
				<button type="button" onclick={() => (creatingFolder = true)} class="inline-flex items-center gap-2 rounded-lg border border-dashed border-primary px-3 py-2 text-sm font-semibold text-primary hover:bg-primary/10"><Plus size={16} />새 폴더</button>
			{/if}
		</div>
	{/if}
	{#snippet footer()}
		<OutlinedButton disabled={downloadLoading || folderCreating} onclick={() => (folderModalOpen = false)}>취소</OutlinedButton>
		<PrimaryButton loading={downloadLoading} disabled={foldersLoading || folderCreating} onclick={() => void startDownload()}><FileDown size={16} /><span>선택한 폴더에 다운로드</span></PrimaryButton>
	{/snippet}
</Modal>

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
