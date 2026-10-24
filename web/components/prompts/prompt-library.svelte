<script lang="ts">
	import { onMount } from 'svelte';
	import { FolderOpen, Save, Pencil, Trash2 } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import LoadingSpinner from '../loadings/loading-spinner.svelte';
	import Toast from '../feedback/toast.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';
	import { appendPrompt, type PromptKind, type SavedPrompt } from '$lib/utils/saved-prompts';

	type Props = { kind: PromptKind; value?: string; disabled?: boolean; manage?: boolean; onchange?: (value: string) => void };
	let { kind, value = '', disabled = false, manage = false, onchange }: Props = $props();
	let rows = $state<SavedPrompt[]>([]);
	let open = $state(false);
	let mode = $state<'save' | 'load'>('load');
	let name = $state('');
	let content = $state('');
	let editingId = $state('');
	let deleteId = $state('');
	let search = $state('');
	let loading = $state(false);
	let saving = $state(false);
	let removingId = $state('');
	let failed = $state(false);
	let error = $state('');
	let notice = $state('');
	let active = true;
	let requestId = 0;
	let busy = $derived(loading || saving || removingId !== '');
	let visible = $derived(rows.filter((row) => `${row.name}\n${row.content}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())));
	onMount(() => { if (manage) void load(); return () => { active = false; requestId += 1; }; });

	async function load() {
		const request = ++requestId;
		loading = true; failed = false; error = '';
		try { const result = await apiJson<SavedPrompt[]>(`saved-prompts?kind=${kind}`); if (active && request === requestId) rows = result; }
		catch (reason) { if (active && request === requestId) { rows = []; failed = true; report(reason); } }
		finally { if (active && request === requestId) loading = false; }
	}
	function beginSave(row?: SavedPrompt) {
		name = row?.name ?? ''; content = row?.content ?? value; editingId = row?.id ?? ''; mode = 'save'; error = ''; notice = ''; open = true;
	}
	function beginLoad() { mode = 'load'; search = ''; notice = ''; open = true; void load(); }
	async function save() {
		if (busy || !name.trim() || !content.trim()) return;
		saving = true; error = '';
		try {
			const row = await apiJson<SavedPrompt>(`saved-prompts${editingId ? `/${editingId}` : ''}`, { method: editingId ? 'PUT' : 'POST', json: { kind, name: name.trim(), content: content.trim() } });
			if (!active) return;
			rows = [row, ...rows.filter((item) => item.id !== row.id)]; open = false; notice = '프롬프트를 저장했습니다.';
		} catch (reason) { if (active) report(reason); }
		finally { if (active) saving = false; }
	}
	async function remove(id: string) {
		if (busy) return;
		removingId = id; error = '';
		try { await apiDelete(`saved-prompts/${id}`); if (active) { rows = rows.filter((item) => item.id !== id); deleteId = ''; notice = '프롬프트를 삭제했습니다.'; } }
		catch (reason) { if (active) report(reason); }
		finally { if (active) removingId = ''; }
	}
	function apply(row: SavedPrompt) {
		if (disabled || busy) return;
		try { onchange?.(appendPrompt(value, row.content, kind)); open = false; notice = '기존 프롬프트 뒤에 추가했습니다.'; }
		catch (reason) { report(reason); }
	}
	function report(reason: unknown) { error = reason instanceof Error ? reason.message : '프롬프트를 처리하지 못했습니다.'; }
</script>

{#snippet list()}
	<div class="space-y-3">
		<label class="block"><span class="sr-only">저장 프롬프트 검색</span><input type="search" bind:value={search} placeholder="이름 또는 내용 검색" class="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" /></label>
		{#if loading}<div class="py-8"><LoadingSpinner label="프롬프트 불러오는 중" /></div>
		{:else if failed}<OutlinedButton onclick={() => void load()}>다시 불러오기</OutlinedButton>
		{:else}
			{#each visible as row (row.id)}
				<article class="space-y-3 rounded-xl border border-border bg-card p-4">
					<h3 class="break-all text-sm font-semibold">{row.name}</h3><p class="max-h-40 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">{row.content}</p>
					<div class="flex flex-wrap items-center justify-end gap-2">
						{#if deleteId === row.id}<span class="text-xs text-destructive">삭제할까요?</span><OutlinedButton disabled={busy} onclick={() => (deleteId = '')}>취소</OutlinedButton><PrimaryButton variant="destructive" loading={removingId === row.id} disabled={busy && removingId !== row.id} onclick={() => void remove(row.id)}>삭제 확인</PrimaryButton>
						{:else}<OutlinedButton disabled={busy} onclick={() => beginSave(row)}><Pencil size={14} />수정</OutlinedButton><OutlinedButton disabled={busy} onclick={() => (deleteId = row.id)}><Trash2 size={14} />삭제</OutlinedButton>{#if !manage}<PrimaryButton disabled={disabled || busy} onclick={() => apply(row)}>뒤에 추가</PrimaryButton>{/if}{/if}
					</div>
				</article>
			{:else}<p class="py-8 text-center text-sm text-muted-foreground">{search.trim() ? '검색 결과가 없습니다.' : '저장된 프롬프트가 없습니다.'}</p>{/each}
		{/if}
	</div>
{/snippet}

<div class="space-y-2" aria-label={`${kind === 'image' ? '이미지' : '동영상'} 저장 프롬프트`}>
	<div class="flex flex-wrap justify-end gap-2">
		<OutlinedButton class="min-h-8 px-2.5 py-1 text-xs" disabled={disabled || busy || (!manage && !value.trim())} onclick={() => beginSave()}><Save size={14} />{manage ? '새 프롬프트' : '프롬프트 저장'}</OutlinedButton>
		{#if !manage}<OutlinedButton class="min-h-8 px-2.5 py-1 text-xs" disabled={disabled || busy} onclick={beginLoad}><FolderOpen size={14} />프롬프트 불러오기</OutlinedButton>{/if}
	</div>
	{#if notice}<p role="status" class="text-xs text-primary">{notice}</p>{/if}
	{#if manage}{@render list()}{/if}
</div>

<Modal bind:open title={mode === 'save' ? editingId ? '프롬프트 수정' : '프롬프트 저장' : '프롬프트 불러오기'} description={mode === 'load' ? '선택한 내용을 기존 입력의 뒤에 추가합니다.' : '프롬프트 문장만 저장합니다.'} closeOnBackdrop={!busy}>
	{#if mode === 'save'}
		<div class="space-y-4">
			<label class="block space-y-2"><span class="text-sm font-medium">이름</span><input bind:value={name} maxlength="100" required disabled={saving} class="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" /></label>
			<label class="block space-y-2"><span class="text-sm font-medium">프롬프트 내용</span><textarea bind:value={content} maxlength="5000" required rows="8" disabled={saving} class="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm leading-6"></textarea></label>
			<div class="flex justify-end gap-2"><OutlinedButton disabled={saving} onclick={() => (open = false)}>취소</OutlinedButton><PrimaryButton loading={saving} disabled={!name.trim() || !content.trim()} onclick={() => void save()}>저장</PrimaryButton></div>
		</div>
	{:else}{@render list()}{/if}
</Modal>
{#if error}<div class="fixed right-4 top-4 z-[80]"><Toast state="negative" title="프롬프트 처리 실패" message={error} onclose={() => (error = '')} /></div>{/if}
