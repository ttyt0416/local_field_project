<script lang="ts">
	import { Folder, FolderUp, Plus } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import LoadingSpinner from '../loadings/loading-spinner.svelte';
	import Toast from '../feedback/toast.svelte';
	import { apiJson } from '$lib/utils/api';
	import { parentModelFolder } from '$lib/utils/model-folders';
	import { modelTypeInfo, type ModelType, type ModelFolder } from '$lib/types/model-storage';

	type Props = {
		open?: boolean;
		modelType: ModelType;
		initialFolder?: string;
		title?: string;
		confirmLabel?: string;
		loading?: boolean;
		onconfirm: (folder: string) => void;
		onclose?: () => void;
	};
	let { open = $bindable(false), modelType, initialFolder = '', title = '폴더 선택', confirmLabel = '선택', loading = false, onconfirm, onclose }: Props = $props();
	let folders = $state<ModelFolder[]>([]);
	let currentFolder = $state('');
	let foldersLoading = $state(false);
	let loadFailed = $state(false);
	let creating = $state(false);
	let newFolderName = $state('');
	let folderCreating = $state(false);
	let error = $state('');
	let requestId = 0;
	let busy = $derived(loading || folderCreating);
	let visibleFolders = $derived(folders.filter((folder) => folder.subfolder && parentModelFolder(folder.subfolder) === currentFolder));

	$effect(() => {
		if (open) void loadFolders(modelType, initialFolder);
		return () => { requestId += 1; };
	});

	async function loadFolders(type: ModelType, initial: string) {
		const request = ++requestId;
		foldersLoading = true;
		loadFailed = false;
		error = '';
		creating = false;
		newFolderName = '';
		try {
			const result = await apiJson<ModelFolder[]>(`models/folders?model_type=${type}`);
			if (request !== requestId) return;
			folders = result;
			currentFolder = result.some((folder) => folder.subfolder === initial) ? initial : '';
		} catch (reason) {
			if (request !== requestId) return;
			loadFailed = true;
			error = reason instanceof Error ? reason.message : '폴더를 불러오지 못했습니다.';
		} finally {
			if (request === requestId) foldersLoading = false;
		}
	}

	function navigate(folder: string) {
		if (busy) return;
		currentFolder = folder;
		creating = false;
		newFolderName = '';
	}

	function close() {
		if (busy) return;
		open = false;
		onclose?.();
	}

	async function createFolder() {
		if (!newFolderName.trim() || busy) return;
		const request = requestId;
		folderCreating = true;
		try {
			const folder = await apiJson<ModelFolder>('models/folders', { method: 'POST', json: { model_type: modelType, parent: currentFolder, name: newFolderName.trim() } });
			if (request !== requestId) return;
			folders = [...folders, folder];
			currentFolder = folder.subfolder;
			creating = false;
			newFolderName = '';
		} catch (reason) {
			if (request === requestId) error = reason instanceof Error ? reason.message : '폴더를 만들지 못했습니다.';
		} finally {
			folderCreating = false;
		}
	}
</script>

<Modal bind:open={() => open, (value) => { if (!value) close(); }} {title} description={`${modelTypeInfo(modelType).label}에서 사용할 폴더를 선택하세요.`} closeOnBackdrop={!busy}>
	{#if foldersLoading}
		<div class="flex min-h-40 items-center justify-center"><LoadingSpinner size="lg" label="폴더를 불러오는 중" /></div>
	{:else if loadFailed}
		<div class="space-y-3 py-6 text-center"><p class="text-sm text-muted-foreground">폴더를 불러오지 못했습니다.</p><OutlinedButton onclick={() => void loadFolders(modelType, initialFolder)}>다시 시도</OutlinedButton></div>
	{:else}
		<div class="space-y-4">
			<div class="flex flex-wrap items-center gap-2">
				<OutlinedButton disabled={busy} active={!currentFolder} class="px-3 text-xs" onclick={() => navigate('')}>{modelTypeInfo(modelType).label}</OutlinedButton>
				{#if currentFolder}<OutlinedButton disabled={busy} class="px-3 text-xs" onclick={() => navigate(parentModelFolder(currentFolder))}><FolderUp size={15} />상위 폴더</OutlinedButton>{/if}
			</div>
			<p class="break-all rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">{modelTypeInfo(modelType).directory}{currentFolder ? ` / ${currentFolder}` : ''}</p>
			<div class="grid max-h-[35dvh] grid-cols-2 gap-2 overflow-y-auto">
				{#each visibleFolders as folder (folder.subfolder)}
					<button type="button" disabled={busy} onclick={() => navigate(folder.subfolder)} class="flex min-w-0 items-center gap-2 rounded-xl border border-border p-3 text-left transition hover:bg-muted disabled:opacity-50"><Folder size={18} class="shrink-0 text-primary" /><span class="truncate text-sm">{folder.subfolder.split('/').at(-1)}</span></button>
				{:else}<p class="col-span-2 py-5 text-center text-sm text-muted-foreground">하위 폴더가 없습니다.</p>{/each}
			</div>
			{#if creating}
				<form class="space-y-3 rounded-xl border border-border p-3" onsubmit={(event) => { event.preventDefault(); void createFolder(); }}>
					<label class="block space-y-2" for="picker-new-folder"><span class="text-sm font-medium">새 폴더 이름</span><input id="picker-new-folder" bind:value={newFolderName} disabled={busy} maxlength="120" class="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></label>
					<div class="flex justify-end gap-2"><OutlinedButton disabled={busy} onclick={() => (creating = false)}>취소</OutlinedButton><PrimaryButton type="submit" loading={folderCreating} disabled={loading || !newFolderName.trim()}>만들기</PrimaryButton></div>
				</form>
			{:else}<OutlinedButton disabled={busy} onclick={() => (creating = true)}><Plus size={16} />새 폴더</OutlinedButton>{/if}
		</div>
	{/if}
	{#snippet footer()}
		<OutlinedButton disabled={busy} onclick={close}>취소</OutlinedButton>
		<PrimaryButton {loading} disabled={foldersLoading || loadFailed || folderCreating} onclick={() => onconfirm(currentFolder)}>{confirmLabel}</PrimaryButton>
	{/snippet}
</Modal>

{#if error}<div class="fixed right-4 top-4 z-[60]"><Toast state="negative" title="폴더 관리 실패" message={error} onclose={() => (error = '')} /></div>{/if}
