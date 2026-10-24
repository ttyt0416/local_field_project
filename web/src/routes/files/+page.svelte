<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ArrowDownWideNarrow, ChevronRight, Download, FileBox, Folder, FolderInput, FolderPlus, HardDrive, Info, LayoutGrid, List, RefreshCw, Trash2, X } from '@lucide/svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import SearchBar from '../../../components/inputs/searchbar.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import ModelFolderPicker from '../../../components/models/model-folder-picker.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';
	import { formatFileSize } from '$lib/utils/generation';
	import { parentModelFolder } from '$lib/utils/model-folders';
	import { modelTypes, modelTypeInfo, type InstalledModel, type ModelFolder, type ModelType } from '$lib/types/model-storage';

	type FolderEntry = { type: ModelType; path: string; name: string; count: number; bytes: number };
	type ToastData = { state: 'positive' | 'negative'; title: string; message: string };
	let ready = $state(false);
	let refreshing = $state(false);
	let loadFailed = $state(false);
	let installed = $state<InstalledModel[]>([]);
	let folders = $state<ModelFolder[]>([]);
	let currentType = $state<ModelType | null>(null);
	let currentFolder = $state('');
	let search = $state('');
	let sort = $state<'name' | 'modified' | 'size'>('name');
	let view = $state<'list' | 'grid'>('list');
	let selectedKey = $state('');
	let selectedModel = $derived(installed.find((model) => fileKey(model) === selectedKey));
	let totalBytes = $derived(installed.reduce((sum, model) => sum + model.size_bytes, 0));
	let query = $derived(search.trim().toLocaleLowerCase());
	let folderEntries = $derived.by(() => {
		const locations = currentType
			? folders.filter((folder) => folder.model_type === currentType && folder.subfolder && (query ? folder.subfolder.startsWith(currentFolder ? `${currentFolder}/` : '') : parentModelFolder(folder.subfolder) === currentFolder)).map((folder) => ({ type: folder.model_type, path: folder.subfolder, name: folder.subfolder.split('/').at(-1)! }))
			: [...modelTypes.map((type) => ({ type: type.value, path: '', name: type.label })), ...(query ? folders.filter((folder) => folder.subfolder).map((folder) => ({ type: folder.model_type, path: folder.subfolder, name: basename(folder.subfolder) })) : [])];
		return locations.filter((folder) => !query || `${folder.name} ${folder.path} ${modelTypeInfo(folder.type).directory}`.toLocaleLowerCase().includes(query)).map((folder): FolderEntry => {
			const files = installed.filter((model) => model.model_type === folder.type && (!folder.path || model.filename.startsWith(`${folder.path}/`)));
			return { ...folder, count: files.length, bytes: files.reduce((sum, model) => sum + model.size_bytes, 0) };
		}).sort((a, b) => sort === 'size' ? b.bytes - a.bytes || a.name.localeCompare(b.name) : a.name.localeCompare(b.name, 'ko', { numeric: true }));
	});
	let visibleFiles = $derived(installed.filter((model) => {
		if (currentType && model.model_type !== currentType) return false;
		if (query) return (!currentFolder || model.filename.startsWith(`${currentFolder}/`)) && `${model.filename} ${modelTypeInfo(model.model_type).label}`.toLocaleLowerCase().includes(query);
		return currentType && parentModelFolder(model.filename) === currentFolder;
	}).sort((a, b) => sort === 'modified' ? Date.parse(b.modified_at) - Date.parse(a.modified_at) || a.filename.localeCompare(b.filename) : sort === 'size' ? b.size_bytes - a.size_bytes || a.filename.localeCompare(b.filename) : basename(a.filename).localeCompare(basename(b.filename), 'ko', { numeric: true })));
	let breadcrumbs = $derived(currentFolder.split('/').filter(Boolean).map((name, index, parts) => ({ name, path: parts.slice(0, index + 1).join('/') })));
	let createModalOpen = $state(false);
	let createType = $state<ModelType>('checkpoint');
	let createParent = $state('');
	let newFolderName = $state('');
	let creating = $state(false);
	let moveTarget = $state<InstalledModel | null>(null);
	let moveModalOpen = $state(false);
	let moving = $state(false);
	let deleteTarget = $state<InstalledModel | null>(null);
	let deleteModalOpen = $state(false);
	let deleting = $state(false);
	let busy = $derived(creating || moving || deleting);
	let toast = $state<ToastData | null>(null);
	let active = true;

	onMount(() => {
		void initialize();
		return () => { active = false; };
	});

	async function initialize() {
		await authStore.initialize();
		if (!active) return;
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		await refresh();
		if (active) ready = true;
	}

	async function refresh() {
		if (refreshing) return;
		refreshing = true;
		try {
			const [files, ...directoryLists] = await Promise.all([
				apiJson<InstalledModel[]>('models/installed'),
				...modelTypes.map((type) => apiJson<ModelFolder[]>(`models/folders?model_type=${type.value}`))
			]);
			if (!active) return;
			installed = files;
			folders = directoryLists.flat();
			loadFailed = false;
			if (currentType && currentFolder && !folders.some((folder) => folder.model_type === currentType && folder.subfolder === currentFolder)) currentFolder = '';
		} catch (reason) {
			if (active) {
				loadFailed = true;
				reportError('파일 목록 조회 실패', reason);
			}
		} finally {
			if (active) refreshing = false;
		}
	}

	function fileKey(model: InstalledModel) {
		return `${model.model_type}:${model.filename}`;
	}

	function basename(path: string) {
		return path.split('/').at(-1) ?? path;
	}

	function navigate(type: ModelType | null, path = '') {
		if (busy) return;
		currentType = type;
		currentFolder = path;
		selectedKey = '';
		search = '';
	}

	function openCreateFolder() {
		createType = currentType ?? 'checkpoint';
		createParent = currentFolder;
		newFolderName = '';
		createModalOpen = true;
	}

	async function createFolder() {
		if (creating || !newFolderName.trim()) return;
		creating = true;
		try {
			const folder = await apiJson<ModelFolder>('models/folders', { method: 'POST', json: { model_type: createType, parent: createParent, name: newFolderName.trim() } });
			if (!active) return;
			folders = [...folders, folder];
			currentType = createType;
			currentFolder = createParent;
			search = '';
			selectedKey = '';
			createModalOpen = false;
			toast = { state: 'positive', title: '폴더 생성 완료', message: `${basename(folder.subfolder)} 폴더를 만들었습니다.` };
		} catch (reason) {
			if (active) reportError('폴더 생성 실패', reason);
		} finally {
			if (active) creating = false;
		}
	}

	function openMove(model: InstalledModel) {
		if (busy) return;
		moveTarget = model;
		moveModalOpen = true;
	}

	async function moveFile(subfolder: string) {
		const target = moveTarget;
		if (!target || busy) return;
		moving = true;
		try {
			const moved = await apiJson<InstalledModel>(`models/installed/${target.model_type}/move`, { method: 'POST', json: { filename: target.filename, subfolder } });
			if (!active) return;
			installed = installed.map((model) => fileKey(model) === fileKey(target) ? moved : model);
			if (selectedKey === fileKey(target)) selectedKey = '';
			moveModalOpen = false;
			toast = { state: 'positive', title: '파일 이동 완료', message: `${basename(moved.filename)} 파일을 이동했습니다.` };
			await refresh();
		} catch (reason) {
			if (active) reportError('파일 이동 실패', reason);
		} finally {
			if (active) moving = false;
		}
	}

	function openDelete(model: InstalledModel) {
		if (busy) return;
		deleteTarget = model;
		deleteModalOpen = true;
	}

	async function deleteFile() {
		const target = deleteTarget;
		if (!target || busy) return;
		deleting = true;
		try {
			const filename = target.filename.split('/').map(encodeURIComponent).join('/');
			await apiDelete(`models/installed/${target.model_type}/${filename}`);
			if (!active) return;
			installed = installed.filter((model) => fileKey(model) !== fileKey(target));
			if (selectedKey === fileKey(target)) selectedKey = '';
			deleteModalOpen = false;
			toast = { state: 'positive', title: '파일 삭제 완료', message: `${basename(target.filename)} 파일을 삭제했습니다.` };
		} catch (reason) {
			if (active) reportError('파일 삭제 실패', reason);
		} finally {
			if (active) deleting = false;
		}
	}

	function reportError(title: string, reason: unknown) {
		toast = { state: 'negative', title, message: reason instanceof Error ? reason.message : '요청을 처리하지 못했습니다.' };
	}

	function formatSize(bytes: number) {
		return bytes === 0 ? '0 B' : formatFileSize(bytes);
	}

	function formatDate(value: string) {
		return new Date(value).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<svelte:head><title>파일 관리 · Local Field</title><meta name="description" content="저장된 모델 파일과 폴더를 탐색하고 정리합니다." /></svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="파일 관리를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<header class="flex flex-wrap items-center justify-between gap-4">
				<div><Typography as="h1" variant="display">파일 관리</Typography><p class="mt-2 text-sm text-muted-foreground">저장된 모델과 폴더를 한곳에서 정리하세요.</p></div>
				<div class="flex items-center gap-2"><OutlinedButton loading={refreshing} disabled={busy} onclick={() => void refresh()}><RefreshCw size={16} /><span class="hidden sm:inline">새로고침</span></OutlinedButton><PrimaryButton disabled={busy || loadFailed || refreshing} onclick={openCreateFolder}><FolderPlus size={17} />새 폴더</PrimaryButton></div>
			</header>

			<div class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card px-5 py-4">
				<div class="flex items-center gap-3"><span class="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><HardDrive size={21} /></span><div><p class="text-sm font-semibold">내 스토리지</p><p class="mt-0.5 text-xs text-muted-foreground">{loadFailed ? '목록을 다시 불러와 주세요.' : `${installed.length}개 파일 · ${formatSize(totalBytes)} 사용 중`}</p></div></div>
				<a href="/models" class="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"><Download size={16} />Civitai에서 다운로드<ChevronRight size={15} /></a>
			</div>

			<div class={`grid items-start gap-5 ${selectedModel ? 'xl:grid-cols-[minmax(0,1fr)_17rem]' : ''}`}>
				<section class="min-w-0 overflow-hidden rounded-2xl border border-border bg-card shadow-sm" aria-label="스토리지 탐색기">
					<div class="space-y-4 border-b border-border p-4 sm:p-5">
						<nav class="flex flex-wrap items-center gap-1 text-sm" aria-label="현재 폴더 경로">
							<button type="button" disabled={busy} onclick={() => navigate(null)} class="rounded-lg px-2 py-1.5 font-semibold transition hover:bg-muted" aria-current={currentType ? undefined : 'page'}>내 스토리지</button>
							{#if currentType}<ChevronRight size={15} class="text-muted-foreground" /><button type="button" disabled={busy} onclick={() => navigate(currentType)} class="rounded-lg px-2 py-1.5 font-medium hover:bg-muted" aria-current={!currentFolder ? 'page' : undefined}>{modelTypeInfo(currentType).label}</button>{/if}
							{#each breadcrumbs as crumb}<ChevronRight size={15} class="text-muted-foreground" /><button type="button" disabled={busy} onclick={() => navigate(currentType, crumb.path)} class="max-w-48 truncate rounded-lg px-2 py-1.5 hover:bg-muted" aria-current={crumb.path === currentFolder ? 'page' : undefined}>{crumb.name}</button>{/each}
						</nav>
						<div class="flex flex-wrap items-center gap-3">
							<SearchBar id="storage-search" bind:value={search} label="파일 및 폴더 검색" placeholder={currentType ? '이 폴더에서 파일 및 폴더 검색' : '스토리지에서 파일 및 폴더 검색'} class="min-w-48 flex-1" oninput={() => (selectedKey = '')} />
							<label class="flex h-10 items-center gap-2 rounded-lg border border-border px-3 text-muted-foreground"><ArrowDownWideNarrow size={16} /><span class="sr-only">파일 정렬</span><select bind:value={sort} aria-label="파일 정렬" class="min-w-0 bg-transparent text-xs font-medium text-foreground focus:outline-none"><option value="name">이름순</option><option value="modified">최근 수정순</option><option value="size">용량순</option></select></label>
							<div class="flex gap-1" role="group" aria-label="파일 표시 방식"><IconOutlinedButton ariaLabel="목록 보기" pressed={view === 'list'} class={view === 'list' ? 'border-primary bg-primary/10 text-primary' : ''} onclick={() => (view = 'list')}><List size={18} /></IconOutlinedButton><IconOutlinedButton ariaLabel="격자 보기" pressed={view === 'grid'} class={view === 'grid' ? 'border-primary bg-primary/10 text-primary' : ''} onclick={() => (view = 'grid')}><LayoutGrid size={17} /></IconOutlinedButton></div>
						</div>
					</div>

					{#if loadFailed}
						<div class="flex min-h-64 flex-col items-center justify-center gap-3 px-5 text-center"><HardDrive size={32} class="text-muted-foreground" /><p class="text-sm text-muted-foreground">파일 목록을 불러오지 못했습니다.</p><OutlinedButton loading={refreshing} onclick={() => void refresh()}>다시 시도</OutlinedButton></div>
					{:else if !folderEntries.length && !visibleFiles.length}
						<div class="flex min-h-72 flex-col items-center justify-center gap-3 px-5 text-center"><Folder size={40} strokeWidth={1.3} class="text-muted-foreground" /><p class="font-medium">{query ? '검색 결과가 없습니다.' : '이 폴더는 비어 있습니다.'}</p><p class="text-sm text-muted-foreground">{query ? '다른 파일명이나 폴더명으로 검색해 보세요.' : '새 폴더를 만들거나 Civitai에서 모델을 다운로드하세요.'}</p></div>
					{:else if view === 'list'}
						<div class="overflow-x-auto">
							<table class="w-full min-w-[36rem] text-left text-sm">
								<thead class="border-b border-border bg-muted/30 text-xs text-muted-foreground"><tr><th scope="col" class="px-5 py-3 font-medium">이름</th><th scope="col" class="whitespace-nowrap px-3 py-3 font-medium">수정한 날짜</th><th scope="col" class="whitespace-nowrap px-3 py-3 text-right font-medium">파일 크기</th><th scope="col" class="w-24 px-3 py-3"><span class="sr-only">파일 작업</span></th></tr></thead>
								<tbody class="divide-y divide-border">
									{#each folderEntries as folder (`${folder.type}:${folder.path}`)}
										<tr class="transition hover:bg-muted/50"><td class="px-5 py-3"><button type="button" disabled={busy} onclick={() => navigate(folder.type, folder.path)} class="flex w-full min-w-0 items-center gap-3 text-left"><Folder size={23} class="shrink-0 fill-primary/15 text-primary" /><span class="min-w-0"><span class="block max-w-64 truncate font-medium">{folder.name}</span><span class="mt-0.5 block text-xs text-muted-foreground">{query && folder.path ? folder.path : `${folder.count}개 파일`}</span></span></button></td><td class="px-3 py-3 text-xs text-muted-foreground">폴더</td><td class="whitespace-nowrap px-3 py-3 text-right text-xs text-muted-foreground">{formatSize(folder.bytes)}</td><td class="px-3 py-3 text-center text-muted-foreground"><ChevronRight size={16} /></td></tr>
									{/each}
									{#each visibleFiles as model (fileKey(model))}
										<tr class={`transition hover:bg-muted/50 ${selectedKey === fileKey(model) ? 'bg-primary/8' : ''}`}><td class="px-5 py-3"><button type="button" aria-label={`${basename(model.filename)} 상세 정보`} aria-pressed={selectedKey === fileKey(model)} onclick={() => (selectedKey = fileKey(model))} class="flex w-full items-center gap-3 text-left"><FileBox size={23} class="shrink-0 text-muted-foreground" /><span class="min-w-0"><span class="block max-w-64 truncate font-medium" title={model.filename}>{basename(model.filename)}</span><span class="mt-0.5 block max-w-64 truncate text-xs text-muted-foreground">{query ? `${modelTypeInfo(model.model_type).label} / ${parentModelFolder(model.filename) || '전체'}` : modelTypeInfo(model.model_type).label}</span></span></button></td><td class="whitespace-nowrap px-3 py-3 text-xs text-muted-foreground">{formatDate(model.modified_at)}</td><td class="whitespace-nowrap px-3 py-3 text-right text-xs text-muted-foreground">{formatSize(model.size_bytes)}</td><td class="px-3 py-3">{@render fileActions(model)}</td></tr>
									{/each}
								</tbody>
							</table>
						</div>
					{:else}
						<div class="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 2xl:grid-cols-3">
							{#each folderEntries as folder (`${folder.type}:${folder.path}`)}
								<button type="button" disabled={busy} onclick={() => navigate(folder.type, folder.path)} class="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-muted/20 p-4 text-left transition hover:border-primary/40 hover:bg-primary/5"><Folder size={30} class="shrink-0 fill-primary/15 text-primary" /><span class="min-w-0"><span class="block truncate font-semibold">{folder.name}</span><span class="mt-1 block text-xs text-muted-foreground">{folder.count}개 파일 · {formatSize(folder.bytes)}</span></span></button>
							{/each}
							{#each visibleFiles as model (fileKey(model))}
								<article class={`min-w-0 overflow-hidden rounded-xl border transition ${selectedKey === fileKey(model) ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'}`}><button type="button" aria-label={`${basename(model.filename)} 상세 정보`} aria-pressed={selectedKey === fileKey(model)} onclick={() => (selectedKey = fileKey(model))} class="block w-full p-4 text-left"><span class="mb-4 flex h-24 items-center justify-center rounded-lg bg-muted/70"><FileBox size={42} strokeWidth={1.3} class="text-primary/70" /></span><span class="block truncate text-sm font-medium" title={model.filename}>{basename(model.filename)}</span><span class="mt-1 block text-xs text-muted-foreground">{modelTypeInfo(model.model_type).label} · {formatSize(model.size_bytes)}</span></button><div class="flex items-center justify-between gap-2 border-t border-border px-3 py-2"><span class="text-xs text-muted-foreground">{formatDate(model.modified_at)}</span>{@render fileActions(model)}</div></article>
							{/each}
						</div>
					{/if}
					<footer class="flex items-center justify-between gap-3 border-t border-border px-5 py-3 text-xs text-muted-foreground"><span>{folderEntries.length}개 폴더 · {visibleFiles.length}개 파일{query ? ' 검색됨' : ''}</span><span>파일을 선택하면 상세 정보를 볼 수 있습니다.</span></footer>
				</section>

				{#if selectedModel}
					<aside class="min-w-0 rounded-2xl border border-border bg-card p-5 shadow-sm" aria-label="파일 상세 정보"><div class="flex items-center justify-between"><h2 class="flex items-center gap-2 text-sm font-semibold"><Info size={16} />파일 정보</h2><IconOutlinedButton ariaLabel="파일 정보 닫기" class="size-8" onclick={() => (selectedKey = '')}><X size={16} /></IconOutlinedButton></div><div class="my-5 flex h-32 items-center justify-center rounded-xl bg-muted"><FileBox size={50} strokeWidth={1.2} class="text-primary/70" /></div><h3 class="break-all text-sm font-semibold leading-6">{basename(selectedModel.filename)}</h3><dl class="mt-5 space-y-4 text-xs"><div><dt class="text-muted-foreground">종류</dt><dd class="mt-1.5 font-medium">{modelTypeInfo(selectedModel.model_type).label}</dd></div><div><dt class="text-muted-foreground">크기</dt><dd class="mt-1.5 font-medium">{formatSize(selectedModel.size_bytes)}</dd></div><div><dt class="text-muted-foreground">위치</dt><dd class="mt-1.5 break-all leading-5">내 스토리지 / {modelTypeInfo(selectedModel.model_type).label}{parentModelFolder(selectedModel.filename) ? ` / ${parentModelFolder(selectedModel.filename)}` : ''}</dd></div><div><dt class="text-muted-foreground">수정한 날짜</dt><dd class="mt-1.5">{formatDate(selectedModel.modified_at)}</dd></div></dl><div class="mt-6 flex flex-wrap gap-2"><OutlinedButton disabled={busy} onclick={() => openMove(selectedModel!)}><FolderInput size={15} />이동</OutlinedButton><OutlinedButton disabled={busy} onclick={() => openDelete(selectedModel!)}><Trash2 size={15} />삭제</OutlinedButton></div></aside>
				{/if}
			</div>
		</div>
	</Layout>
{/if}

{#snippet fileActions(model: InstalledModel)}
	<div class="flex justify-end gap-1"><IconOutlinedButton ariaLabel={`${basename(model.filename)} 이동`} title="폴더 이동" variant="filled" class="size-8" disabled={busy || refreshing} loading={moving && moveTarget !== null && fileKey(moveTarget) === fileKey(model)} onclick={() => openMove(model)}><FolderInput size={16} /></IconOutlinedButton><IconOutlinedButton ariaLabel={`${basename(model.filename)} 삭제`} title="삭제" variant="filled" class="size-8 hover:bg-destructive/10 hover:text-destructive" disabled={busy || refreshing} loading={deleting && deleteTarget !== null && fileKey(deleteTarget) === fileKey(model)} onclick={() => openDelete(model)}><Trash2 size={16} /></IconOutlinedButton></div>
{/snippet}

<Modal bind:open={() => createModalOpen, (value) => { if (!creating) createModalOpen = value; }} title="새 폴더" description="현재 위치에 파일을 정리할 폴더를 만드세요." closeOnBackdrop={!creating}>
	<form id="storage-create-folder" class="space-y-4" onsubmit={(event) => { event.preventDefault(); void createFolder(); }}>
		{#if !currentType}<label class="block space-y-2" for="storage-folder-type"><span class="text-sm font-medium">저장 위치</span><select id="storage-folder-type" bind:value={createType} disabled={creating} class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm">{#each modelTypes as type}<option value={type.value}>{type.label}</option>{/each}</select></label>{/if}
		<p class="break-all text-xs text-muted-foreground">내 스토리지 / {modelTypeInfo(createType).label}{createParent ? ` / ${createParent}` : ''}</p>
		<label class="block space-y-2" for="storage-new-folder"><span class="text-sm font-medium">폴더 이름</span><input id="storage-new-folder" bind:value={newFolderName} disabled={creating} maxlength="120" placeholder="새 폴더 이름" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></label>
	</form>
	{#snippet footer()}<OutlinedButton disabled={creating} onclick={() => (createModalOpen = false)}>취소</OutlinedButton><PrimaryButton loading={creating} disabled={!newFolderName.trim()} onclick={() => void createFolder()}>만들기</PrimaryButton>{/snippet}
</Modal>

{#if moveTarget}<ModelFolderPicker bind:open={moveModalOpen} modelType={moveTarget.model_type} initialFolder={parentModelFolder(moveTarget.filename)} title="파일 이동" confirmLabel="이 폴더로 이동" loading={moving} onconfirm={(folder) => void moveFile(folder)} onclose={() => void refresh()} />{/if}

<Modal bind:open={() => deleteModalOpen, (value) => { if (!deleting) deleteModalOpen = value; }} title="파일을 삭제하시겠습니까?" description="삭제한 파일은 복구할 수 없습니다." closeOnBackdrop={!deleting}>
	<p class="break-all text-sm leading-6"><strong>{deleteTarget?.filename}</strong> 파일을 스토리지에서 삭제합니다.</p>
	{#snippet footer()}<OutlinedButton disabled={deleting} onclick={() => (deleteModalOpen = false)}>취소</OutlinedButton><PrimaryButton loading={deleting} variant="destructive" onclick={() => void deleteFile()}><Trash2 size={16} />삭제</PrimaryButton>{/snippet}
</Modal>

{#if toast}<div class="fixed right-4 top-4 z-[60]"><Toast state={toast.state} title={toast.title} message={toast.message} onclose={() => (toast = null)} /></div>{/if}
