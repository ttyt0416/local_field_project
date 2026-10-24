<script lang="ts">
	import { onMount } from 'svelte';
	import { KeyRound } from '@lucide/svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import Toast from '../feedback/toast.svelte';
	import { apiJson } from '$lib/utils/api';
	import type { DownloadProvider } from '$lib/types/model-downloads';

	type Status = { provider: DownloadProvider; saved: boolean; server_configured: boolean; updated_at: string | null };
	let { provider }: { provider: DownloadProvider } = $props();
	let statuses = $state<Status[]>([]);
	let token = $state('');
	let loading = $state(true);
	let saving = $state(false);
	let deleting = $state(false);
	let failed = $state(false);
	let message = $state('');
	let error = $state('');
	let active = true;
	let current = $derived(statuses.find((item) => item.provider === provider));
	let label = $derived(provider === 'civitai' ? 'Civitai' : 'Hugging Face');
	$effect(() => { provider; token = ''; message = ''; error = ''; });
	onMount(() => { void load(); return () => { active = false; }; });

	async function load() {
		loading = true;
		failed = false;
		try { const result = await apiJson<Status[]>('models/tokens'); if (active) statuses = result; }
		catch (reason) { if (active) { failed = true; report(reason); } }
		finally { if (active) loading = false; }
	}
	async function save(remove = false) {
		if (saving || deleting || loading) return;
		const selected = provider;
		if (remove) deleting = true; else saving = true;
		error = ''; message = '';
		try {
			const result = await apiJson<Status[]>(`models/tokens/${selected}`, { method: remove ? 'DELETE' : 'PUT', ...(remove ? {} : { json: { token: token.trim() } }) });
			if (!active) return;
			statuses = result;
			if (selected === provider) { token = ''; message = remove ? '개인 토큰을 삭제했습니다.' : 'API 토큰을 저장했습니다.'; }
		} catch (reason) { if (active) report(reason); }
		finally { if (active) { saving = false; deleting = false; } }
	}
	function report(reason: unknown) { error = reason instanceof Error ? reason.message : 'API 토큰을 처리하지 못했습니다.'; }
</script>

<section class="space-y-3 rounded-2xl border border-border bg-card p-5" aria-label={`${label} API 토큰`}>
	<div class="flex flex-wrap items-center justify-between gap-2"><h2 class="flex items-center gap-2 text-sm font-semibold"><KeyRound size={16} />{label} API 토큰</h2><span class="text-xs text-muted-foreground" role="status">{loading ? '확인 중' : failed ? '조회 실패' : current?.saved ? '개인 토큰 등록됨' : current?.server_configured ? '서버 기본 토큰 사용 중' : '등록된 토큰 없음'}</span></div>
	{#if failed}<OutlinedButton loading={loading} onclick={() => void load()}>다시 조회</OutlinedButton>{:else}
	<form class="flex flex-wrap gap-2" onsubmit={(event) => { event.preventDefault(); void save(); }}>
		<label class="sr-only" for="download-api-token">{label} API 토큰 입력</label><input id="download-api-token" type="password" autocomplete="new-password" bind:value={token} maxlength="4096" disabled={loading || saving || deleting} placeholder={current?.saved ? '변경할 API 토큰 입력' : 'API 토큰 입력'} class="min-w-40 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm" />
		<PrimaryButton type="submit" loading={saving} disabled={loading || deleting || !token.trim()}>토큰 저장</PrimaryButton>
		{#if current?.saved}<OutlinedButton loading={deleting} disabled={loading || saving} onclick={() => void save(true)}>개인 토큰 삭제</OutlinedButton>{/if}
	</form>{/if}
	<p class="text-xs leading-5 text-muted-foreground">내 계정에 암호화해 저장하고 다음 조회·다운로드부터 적용합니다. 개인 토큰이 없으면 서버 기본 토큰을 사용합니다.{#if provider === 'hugging_face'} 공개 모델은 토큰 없이도 다운로드할 수 있습니다.{/if}</p>
	{#if message}<p role="status" class="text-xs text-primary">{message}</p>{/if}
	{#if error}<p role="alert" class="text-xs text-destructive">{error}</p><div class="fixed right-4 top-4 z-[80]"><Toast state="negative" title="API 토큰 처리 실패" message={error} onclose={() => (error = '')} /></div>{/if}
</section>
