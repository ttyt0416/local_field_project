<script lang="ts">
	import { onMount } from 'svelte';
	import { Download, FileDown } from '@lucide/svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import LoadingSpinner from '../loadings/loading-spinner.svelte';
	import SearchBar from '../inputs/searchbar.svelte';
	import ModelFolderPicker from '../models/model-folder-picker.svelte';
	import Toast from '../feedback/toast.svelte';
	import { apiJson } from '$lib/utils/api';
	import { formatFileSize } from '$lib/utils/generation';
	import { modelTypes, modelTypeInfo, type ModelType } from '$lib/types/model-storage';
	import type { DownloadJob } from '$lib/types/model-downloads';

	type HuggingFaceLookup = {
		repo_id: string;
		revision: string;
		requested_revision: string;
		files: { path: string; size_bytes: number | null; sha256: string | null }[];
		selected_file_path: string;
	};
	type Props = { busy?: boolean; ondownload: (job: DownloadJob) => void };
	let { busy = $bindable(false), ondownload }: Props = $props();
	let source = $state('');
	let revision = $state('');
	let modelType = $state<ModelType>('checkpoint');
	let lookup = $state<HuggingFaceLookup | null>(null);
	let selectedPath = $state('');
	let searching = $state(false);
	let downloading = $state(false);
	let folderModalOpen = $state(false);
	let fileSearch = $state('');
	let error = $state('');
	let toastError = $state('');
	let active = true;
	let requestId = 0;
	let visibleFiles = $derived(lookup?.files.filter((file) => file.path.toLocaleLowerCase().includes(fileSearch.trim().toLocaleLowerCase())) ?? []);
	let selectedFile = $derived(lookup?.files.find((file) => file.path === selectedPath));
	$effect(() => { busy = searching || downloading; });
	onMount(() => () => { active = false; requestId += 1; });

	function resetLookup() {
		requestId += 1;
		lookup = null;
		selectedPath = '';
		fileSearch = '';
		error = '';
		searching = false;
	}

	async function searchRepository() {
		if (!source.trim() || downloading) return;
		const request = ++requestId;
		searching = true;
		error = '';
		try {
			const result = await apiJson<HuggingFaceLookup>(`models/hugging-face/lookup?source=${encodeURIComponent(source.trim())}&revision=${encodeURIComponent(revision.trim())}`, { timeout: 60_000 });
			if (!active || request !== requestId) return;
			lookup = result;
			selectedPath = result.selected_file_path;
			fileSearch = '';
		} catch (reason) {
			if (!active || request !== requestId) return;
			lookup = null;
			reportError(reason, 'Hugging Face 파일 목록을 조회하지 못했습니다.');
		} finally {
			if (active && request === requestId) searching = false;
		}
	}

	async function startDownload(folder: string) {
		const selected = lookup;
		if (!selected || !selectedPath || downloading) return;
		downloading = true;
		error = '';
		try {
			const job = await apiJson<DownloadJob>('models/hugging-face/download', {
				method: 'POST', timeout: 60_000,
				json: { repo_id: selected.repo_id, revision: selected.revision, filename: selectedPath, model_type: modelType, subfolder: folder }
			});
			if (!active) return;
			folderModalOpen = false;
			ondownload(job);
			resetLookup();
			source = '';
			revision = '';
		} catch (reason) {
			if (active) reportError(reason, 'Hugging Face 다운로드를 요청하지 못했습니다.');
		} finally {
			if (active) downloading = false;
		}
	}

	function reportError(reason: unknown, fallback: string) {
		error = reason instanceof Error ? reason.message : fallback;
		toastError = error;
	}
</script>

<section class="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-sm" aria-label="Hugging Face 다운로드">
	<div class="flex flex-wrap gap-2" role="group" aria-label="Hugging Face 저장 모델 종류">
		{#each modelTypes as type}<button type="button" disabled={downloading} aria-pressed={modelType === type.value} onclick={() => (modelType = type.value)} class={`rounded-lg border px-3 py-2 text-sm font-semibold transition disabled:opacity-50 ${modelType === type.value ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'}`}>{type.label}</button>{/each}
	</div>
	<form class="space-y-3" onsubmit={(event) => { event.preventDefault(); void searchRepository(); }}>
		<label class="block space-y-2" for="hugging-face-source"><span class="text-sm font-medium">저장소 또는 파일 링크</span><input id="hugging-face-source" bind:value={source} oninput={resetLookup} disabled={downloading} placeholder="https://huggingface.co/owner/repo 또는 owner/repo" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></label>
		<div class="flex flex-wrap items-end gap-3"><label class="min-w-48 flex-1 space-y-2" for="hugging-face-revision"><span class="block text-sm font-medium">리비전 <span class="font-normal text-muted-foreground">(선택)</span></span><input id="hugging-face-revision" bind:value={revision} oninput={resetLookup} disabled={downloading} placeholder="비워 두면 링크의 리비전 또는 main" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></label><PrimaryButton type="submit" loading={searching} disabled={downloading || !source.trim()}><Download size={16} />파일 조회</PrimaryButton></div>
	</form>
	<p class="text-xs leading-5 text-muted-foreground">저장소·폴더 링크 또는 blob/resolve 파일 링크를 지원합니다. 저장할 모델 종류를 선택해 주세요.</p>
</section>

{#if lookup}
	<section class="space-y-4 rounded-2xl border border-primary/30 bg-primary/5 p-5" aria-label="Hugging Face 파일 선택">
		<div><p class="break-all text-lg font-semibold">{lookup.repo_id}</p><p class="mt-1 break-all text-xs text-muted-foreground">리비전 {lookup.requested_revision} · {lookup.revision.slice(0, 12)}</p><p class="mt-2 text-sm text-primary">저장 종류: {modelTypeInfo(modelType).label}</p></div>
		<SearchBar id="hugging-face-file-search" bind:value={fileSearch} label="Hugging Face 파일 검색" placeholder="파일명 또는 경로로 검색" disabled={downloading} />
		<div class="flex items-center justify-between text-sm"><p class="font-semibold">다운로드할 파일</p><span class="text-xs text-muted-foreground">{visibleFiles.length} / {lookup.files.length}개</span></div>
		<div class="max-h-80 space-y-2 overflow-y-auto pr-1">
			{#each visibleFiles as file (file.path)}<button type="button" disabled={downloading} aria-pressed={selectedPath === file.path} onclick={() => (selectedPath = file.path)} class={`flex w-full min-w-0 items-center justify-between gap-3 rounded-lg border p-3 text-left transition disabled:opacity-50 ${selectedPath === file.path ? 'border-primary bg-background ring-1 ring-primary' : 'border-border bg-background/60 hover:bg-background'}`}><span class="min-w-0"><span class="block truncate text-sm font-medium" title={file.path}>{file.path}</span><span class="mt-1 block text-xs text-muted-foreground">{formatFileSize(file.size_bytes)}{file.sha256 ? ' · SHA-256 확인' : ''}</span></span><span class="shrink-0 text-xs text-muted-foreground">{selectedPath === file.path ? '선택됨' : '선택'}</span></button>{:else}<p class="py-6 text-center text-sm text-muted-foreground">검색 결과가 없습니다.</p>{/each}
		</div>
		{#if selectedFile}<p class="break-all text-xs text-muted-foreground">선택한 파일: {selectedFile.path}</p>{/if}
		<div class="flex justify-end"><PrimaryButton disabled={!selectedPath || searching} loading={downloading} onclick={() => (folderModalOpen = true)}><FileDown size={16} />저장 폴더 선택</PrimaryButton></div>
	</section>
{/if}

{#if error}<div class="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">{error}</div>{/if}
{#if toastError}<div class="fixed right-4 top-4 z-[60]"><Toast state="negative" title="Hugging Face 다운로드 실패" message={toastError} onclose={() => (toastError = '')} /></div>{/if}

<ModelFolderPicker bind:open={folderModalOpen} {modelType} title="저장 폴더 선택" confirmLabel="선택한 폴더에 다운로드" loading={downloading} onconfirm={(folder) => void startDownload(folder)} />
