<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Bone, Download, X } from '@lucide/svelte';
	import ModelViewer from '../../../../components/media/model-viewer.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import Select from '../../../../components/inputs/select.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { apiForm, apiJson } from '$lib/utils/api';
	import { downloadMedia } from '$lib/utils/download';
	import { formatElapsedSeconds, formatKstDateTime } from '$lib/utils/generation';

	type Source = { id: string; generation_mode?: string; status: string; model_url: string | null; created_at: string };
	type SourcePage = { items: Source[]; total_pages: number };
	type Accepted = { prompt_id: string; client_id: string; generation_id: string; status: 'queued'; stage: string; created_at: string; elapsed_seconds: number };
	const inputTabs = [{ value: 'file' as const, label: '파일 업로드' }, { value: 'vault' as const, label: '보관함 MESH' }];
	const stages: Record<string, string> = { queued: '리깅 대기 중', loading_model: '리깅 모델 준비 중', preprocessing: '메시 분석 중', rigging: '뼈대와 스킨 가중치 생성 중', skinning: '스킨 가중치 적용 중', exporting: '리깅된 GLB 내보내는 중', storage: '결과 저장 중', completed: '리깅 완료', cancelled: '리깅 취소됨', failed: '리깅 실패' };
	const inputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20';
	let ready = $state(false);
	let available = $state(false);
	let detail = $state('');
	let inputMode = $state<'file' | 'vault'>('file');
	let file = $state<File | null>(null);
	let sourceId = $state('');
	let sources = $state<Source[]>([]);
	let sourcePage = $state(0);
	let totalPages = $state(1);
	let loadingSources = $state(false);
	let temperature = $state(1);
	let beams = $state(10);
	let submitting = $state(false);
	let cancelling = $state(false);
	let downloading = $state(false);
	let jobKey = $state('');
	let error = $state('');
	let success = $state('');
	let announced = $state('');
	let mounted = true;
	let job = $derived(jobKey ? generationJobStore.jobs[jobKey] : undefined);
	let busy = $derived(submitting || job?.status === 'queued' || job?.status === 'processing');
	let source = $derived(sources.find((item) => item.id === sourceId));
	let preview = $derived(inputMode === 'file' ? file : source?.model_url);
	let sourceOptions = $derived(sources.map((item) => ({ value: item.id, label: `${formatKstDateTime(item.created_at)} · ${item.id.slice(0, 8)}` })));
	let stage = $derived(job ? stages[job.stage ?? job.status] ?? '리깅 처리 중' : '');

	onMount(() => {
		void initialize();
		return () => { mounted = false; };
	});

	$effect(() => {
		if (!job || (job.status !== 'completed' && job.status !== 'failed')) return;
		const key = `${job.key}:${job.status}`;
		if (announced === key) return;
		announced = key;
		if (job.status === 'completed') success = '리깅된 GLB를 보관함에 저장했습니다.';
		else error = job.error ?? '리깅에 실패했습니다.';
	});

	async function initialize() {
		try {
			await authStore.initialize();
			if (!authStore.isAuthenticated) { await goto('/login'); return; }
			await generationJobStore.initialize();
			const existing = generationJobStore.list.find((item) => item.kind === '3d' && item.generationMode === 'rigging');
			if (existing) { jobKey = existing.key; announced = `${existing.key}:${existing.status}`; }
			const options = await apiJson<{ ready: boolean; detail: string }>('generation/3d/rigging/options');
			available = options.ready;
			detail = options.detail;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '리깅 설정을 불러오지 못했습니다.';
		} finally { ready = true; }
	}

	async function loadSources() {
		if (loadingSources || sourcePage >= totalPages) return;
		loadingSources = true;
		try {
			const result = await apiJson<SourcePage>(`vault/3d?page=${sourcePage + 1}`);
			sources = [...sources, ...result.items.filter((item) => item.status === 'completed' && item.generation_mode !== 'rigging')];
			sourcePage += 1;
			totalPages = result.total_pages;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '보관함 모델을 불러오지 못했습니다.';
		} finally { loadingSources = false; }
	}

	function selectFile(event: Event) {
		if (!(event.currentTarget instanceof HTMLInputElement)) return;
		const selected = event.currentTarget.files?.[0] ?? null;
		if (selected && (!selected.name.toLowerCase().endsWith('.glb') || selected.size > 200 * 1024 * 1024)) {
			error = '200MB 이하의 GLB 파일을 선택해 주세요.';
			file = null;
			event.currentTarget.value = '';
			return;
		}
		file = selected;
	}

	async function generate() {
		if (busy || !available) return;
		if ((inputMode === 'file' && !file) || (inputMode === 'vault' && !sourceId)) { error = '리깅할 GLB 모델을 선택해 주세요.'; return; }
		if (!Number.isFinite(temperature) || temperature < .1 || temperature > 2 || !Number.isInteger(beams) || beams < 1 || beams > 10) { error = '리깅 설정을 확인해 주세요.'; return; }
		error = ''; success = ''; jobKey = ''; submitting = true;
		const form = new FormData();
		if (inputMode === 'file' && file) form.append('file', file, file.name);
		form.append('payload', JSON.stringify({ source_generation_id: inputMode === 'vault' ? sourceId : null, temperature, num_beams: beams }));
		try {
			const accepted = await apiForm<Accepted>('generation/3d/rigging', form, { timeout: 180_000 });
			const key = generationJobStore.track({ kind: '3d', generationMode: 'rigging', promptId: accepted.prompt_id, clientId: accepted.client_id, generationId: accepted.generation_id, status: accepted.status, stage: accepted.stage, createdAt: Date.parse(accepted.created_at), elapsedSeconds: accepted.elapsed_seconds });
			if (mounted) jobKey = key;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '리깅 작업을 시작하지 못했습니다.';
		} finally { submitting = false; }
	}

	async function cancel() {
		cancelling = true;
		try { await generationJobStore.cancel(jobKey); }
		catch (reason) { error = reason instanceof Error ? reason.message : '리깅을 취소하지 못했습니다.'; }
		finally { cancelling = false; }
	}

	async function download() {
		if (!job?.modelUrl) return;
		downloading = true;
		try { await downloadMedia(job.modelUrl, job.modelFilename ?? 'rigged-model.glb'); }
		catch (reason) { error = reason instanceof Error ? reason.message : 'GLB를 다운로드하지 못했습니다.'; }
		finally { downloading = false; }
	}
</script>

{#if !ready}
	<div class="flex min-h-80 items-center justify-center"><LoadingSpinner size="lg" label="리깅 설정을 불러오는 중" /></div>
{:else}
	<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
		<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="rigging-result-title">
			<div class="flex items-center justify-between gap-4"><div><div id="rigging-result-title"><Typography as="h2" variant="h2">리깅 결과</Typography></div>{#if job}<p class="mt-1 text-sm text-muted-foreground">{stage} · {formatElapsedSeconds(generationJobStore.elapsedSeconds(job, generationJobStore.now))}</p>{/if}</div><Bone size={22} class="text-primary" /></div>
			<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
				{#if job?.modelUrl}
					<ModelViewer source={job.modelUrl} sourceType="server" alt="리깅된 3D 모델" autoRotate class="min-h-[24rem] sm:min-h-[34rem]" />
				{:else if busy}
					<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 px-6 text-center sm:min-h-[34rem]"><LoadingSpinner size="lg" label={submitting ? '모델 업로드 중' : stage} /><p class="text-sm font-medium">{submitting ? '모델 업로드 중' : stage}</p>{#if job}<p class="text-lg font-semibold tabular-nums text-primary">경과 {formatElapsedSeconds(generationJobStore.elapsedSeconds(job, generationJobStore.now))}</p>{#if job.queuePosition !== null}<p class="text-xs text-muted-foreground">대기 {job.queuePosition}번째</p>{/if}{/if}</div>
				{:else}
					<div class="flex min-h-[24rem] flex-col items-center justify-center gap-3 px-6 text-center sm:min-h-[34rem]"><Bone size={30} class="text-primary" /><p class="text-sm font-medium">GLB 모델에 뼈대와 스킨 가중치를 추가합니다.</p><p class="max-w-sm text-xs leading-5 text-muted-foreground">파일을 업로드하거나 보관함의 MESH 결과를 선택해 주세요.</p></div>
				{/if}
			</div>
			{#if busy && jobKey}<OutlinedButton class="mt-4 w-full" loading={cancelling} disabled={cancelling} onclick={() => void cancel()}><X size={16} />리깅 취소</OutlinedButton>{/if}
			{#if job?.modelUrl}<div class="mt-4 flex flex-wrap items-center gap-4"><OutlinedButton loading={downloading} onclick={() => void download()}><Download size={16} />GLB 다운로드</OutlinedButton><a href={`/vault/3d/${job.generationId}`} class="text-sm font-semibold text-primary hover:underline">보관함에서 상세 보기</a></div><p class="mt-3 text-xs text-muted-foreground">뼈대와 스킨 가중치가 포함된 결과입니다. 동작 애니메이션은 별도로 적용해 주세요.</p>{/if}
		</section>
		<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="rigging-settings-title">
			<div id="rigging-settings-title"><Typography as="h2" variant="h2">자동 리깅 설정</Typography></div>
			<p class="mt-2 text-xs leading-5 text-muted-foreground"><a href="https://github.com/VAST-AI-Research/SkinTokens" target="_blank" rel="noreferrer" class="font-semibold text-primary hover:underline">SkinTokens</a> · 캐릭터 메시에서 뼈대와 스킨 가중치를 자동으로 생성합니다. 입력 메시의 형태에 따라 결과 품질이 달라집니다.</p>
			{#if detail}<p class="mt-3 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">{detail}</p>{/if}
			<form class="mt-5 space-y-5 pb-24 sm:pb-0" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
				<Tab items={inputTabs.map((item) => ({ ...item, disabled: busy }))} bind:value={inputMode} ariaLabel="리깅 소스" onselect={(value) => { if (value === 'vault' && sourcePage === 0) void loadSources(); }} />
				{#if inputMode === 'file'}
					<div class="space-y-2"><label for="rigging-file" class="text-sm font-medium">소스 GLB</label><input id="rigging-file" type="file" accept=".glb,model/gltf-binary" disabled={busy} onchange={selectFile} class="block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-primary" /><p class="text-xs text-muted-foreground">200MB 이하 · 리깅되지 않은 GLB 메시</p></div>
				{:else}
					<Select id="rigging-source" label="보관함 MESH" options={sourceOptions} bind:value={sourceId} placeholder="리깅할 모델 선택" disabled={busy || loadingSources} />
					{#if !sources.length && !loadingSources}<p class="text-xs text-muted-foreground">이 페이지에 완료된 MESH 결과가 없습니다.</p>{/if}
					{#if sourcePage < totalPages}<OutlinedButton class="w-full" loading={loadingSources} disabled={busy} onclick={() => void loadSources()}>보관함 모델 더 불러오기</OutlinedButton>{/if}
				{/if}
				{#if preview}<ModelViewer source={preview} sourceType={inputMode === 'file' ? 'local' : 'server'} alt="리깅할 원본 메시" class="h-64" />{/if}
				<details class="rounded-xl border border-border p-3"><summary class="cursor-pointer text-sm font-medium">고급 설정</summary><div class="mt-4 grid grid-cols-2 gap-3"><label for="rigging-temperature" class="space-y-2 text-sm"><span>Temperature</span><input id="rigging-temperature" type="number" min="0.1" max="2" step="0.1" bind:value={temperature} disabled={busy} required class={inputClass} /></label><label for="rigging-beams" class="space-y-2 text-sm"><span>Beam 수</span><input id="rigging-beams" type="number" min="1" max="10" step="1" bind:value={beams} disabled={busy} required class={inputClass} /></label></div><p class="mt-2 text-xs leading-5 text-muted-foreground">Beam 수가 높을수록 더 많은 뼈대 후보를 탐색하며 처리 시간이 늘어납니다.</p></details>
				<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"><PrimaryButton type="submit" loading={busy} deactive={!available} disabled={inputMode === 'file' ? !file : !sourceId} class="w-full"><Bone size={17} /><span>{busy ? '리깅 처리 중' : available ? '자동 리깅' : 'SkinTokens 연결 대기 중'}</span></PrimaryButton></div>
			</form>
		</section>
	</div>
{/if}

{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="리깅 처리 오류" message={error} onclose={() => (error = '')} /></div>{:else if success}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="리깅 완료" message={success} onclose={() => (success = '')} /></div>{/if}
