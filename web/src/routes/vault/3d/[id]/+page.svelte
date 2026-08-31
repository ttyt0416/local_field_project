<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { ArrowLeft, Box, Download, Heart, Trash2 } from '@lucide/svelte';
	import ImageMedia from '../../../../../components/media/image.svelte';
	import ModelViewer from '../../../../../components/media/model-viewer.svelte';
	import LoadingSpinner from '../../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../../components/buttons/outlined-button.svelte';
	import IconOutlinedButton from '../../../../../components/buttons/icon-outlined-button.svelte';
	import PrimaryButton from '../../../../../components/buttons/primary-button.svelte';
	import Toast from '../../../../../components/feedback/toast.svelte';
	import Modal from '../../../../../components/modals/modal.svelte';
	import Typography from '../../../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';
	import { downloadMedia } from '$lib/utils/download';
	import { formatElapsedSeconds, formatFileSize, formatKstDateTime } from '$lib/utils/generation';

	type Vault3DDetail = {
		id: string;
		media_type: '3d';
		status: string;
		stage?: string;
		preset: 'preview' | 'standard' | 'high';
		seed: number | null;
		model_url: string | null;
		source_image_url: string | null;
		view_count: number;
		is_favorite: boolean;
		created_at: string;
		completed_at: string | null;
		elapsed_seconds: number;
		file_size_bytes: number | null;
		remove_background: boolean;
		padding: number;
		source_filename: string;
	};

	let ready = $state(false);
	let generation = $state<Vault3DDetail | null>(null);
	let error = $state('');
	let deleteModalOpen = $state(false);
	let deleting = $state(false);
	let favoriteUpdating = $state(false);
	let downloading = $state(false);

	onMount(() => {
		void loadDetail();
	});

	async function loadDetail() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		const generationId = page.params.id;
		if (!generationId) {
			error = '3D 생성 결과 식별자가 없습니다.';
			ready = true;
			return;
		}
		try {
			generation = await apiJson<Vault3DDetail>(`vault/3d/${generationId}`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '3D 모델 상세 정보를 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	async function toggleFavorite() {
		if (!generation || favoriteUpdating) return;
		favoriteUpdating = true;
		try {
			const result = await apiJson<{ is_favorite: boolean }>(`vault/3d/${generation.id}/favorite`, {
				method: 'PATCH',
				json: { is_favorite: !generation.is_favorite }
			});
			generation = { ...generation, is_favorite: result.is_favorite };
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '즐겨찾기를 변경하지 못했습니다.';
		} finally {
			favoriteUpdating = false;
		}
	}

	async function downloadModel() {
		if (!generation?.model_url || downloading) return;
		downloading = true;
		try {
			await downloadMedia(generation.model_url, `local-field-3d-${generation.id}.glb`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '3D 모델을 다운로드하지 못했습니다.';
		} finally {
			downloading = false;
		}
	}

	async function deleteModel() {
		if (!generation || deleting) return;
		deleting = true;
		try {
			await apiDelete(`vault/3d/${generation.id}`);
			deleteModalOpen = false;
			await goto('/vault?tab=3d');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '3D 모델을 삭제하지 못했습니다.';
		} finally {
			deleting = false;
		}
	}

	function presetLabel(preset: Vault3DDetail['preset']) {
		return { preview: '미리보기', standard: '표준', high: '고품질' }[preset];
	}

	function statusLabel(status: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패', cancelled: '취소됨' }[status] ?? status;
	}

	function imageSourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}
</script>

<svelte:head>
	<title>3D 모델 상세 · Local Field</title>
	<meta name="description" content="생성된 TRELLIS.2 3D 모델 상세" />
</svelte:head>

{#if !ready}
	<div class="min-h-screen bg-muted/30 px-4 py-8 text-foreground dark:bg-background sm:px-6 lg:px-8">
		<main class="mx-auto max-w-6xl space-y-6">
			<a href="/vault?tab=3d" class="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-foreground"><ArrowLeft size={16} strokeWidth={1.8} />보관함으로 돌아가기</a>
			<section><Typography as="h1" variant="display">3D 모델 상세</Typography><div class="flex min-h-[24rem] items-center justify-center"><LoadingSpinner size="lg" label="3D 모델 상세 정보를 불러오는 중" /></div></section>
		</main>
	</div>
{:else if generation}
	<div class="min-h-screen bg-muted/30 px-4 py-8 text-foreground dark:bg-background sm:px-6 lg:px-8">
		<main class="mx-auto max-w-6xl space-y-6">
			<a href="/vault?tab=3d" class="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-foreground"><ArrowLeft size={16} strokeWidth={1.8} />보관함으로 돌아가기</a>
			<section>
				<Typography as="h1" variant="display">3D 모델 상세</Typography>
				<p class="mt-3 text-sm text-muted-foreground">생성 시작 {formatKstDateTime(generation.created_at)} · 소요 {formatElapsedSeconds(generation.elapsed_seconds)} · 용량 {formatFileSize(generation.file_size_bytes)} · 조회 {generation.view_count}</p>
			</section>

			<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<div class="relative overflow-hidden rounded-xl bg-muted">
						{#if generation.model_url}
							<ModelViewer source={generation.model_url} sourceType="server" poster={generation.source_image_url ?? undefined} alt="생성된 3D 모델" autoRotate class="min-h-[24rem] sm:min-h-[36rem]" />
						{:else}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-2 text-sm text-muted-foreground"><Box size={28} strokeWidth={1.7} />3D 모델 결과가 아직 없습니다.</div>
						{/if}
						<div class="absolute bottom-3 right-3 z-10 flex gap-2">
							<IconOutlinedButton ariaLabel="3D 모델 다운로드" loading={downloading} disabled={!generation.model_url} class="bg-card/90 shadow-lg" onclick={() => void downloadModel()}><Download size={18} strokeWidth={1.9} /></IconOutlinedButton>
							<IconOutlinedButton variant="filled" ariaLabel={generation.is_favorite ? '즐겨찾기 해제' : '즐겨찾기 추가'} pressed={generation.is_favorite} loading={favoriteUpdating} class={generation.is_favorite ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-card/90'} onclick={() => void toggleFavorite()}><Heart size={18} strokeWidth={1.9} fill={generation.is_favorite ? 'currentColor' : 'none'} /></IconOutlinedButton>
						</div>
					</div>
					<p class="mt-3 text-xs text-muted-foreground">드래그로 회전하고 스크롤 또는 핀치로 확대할 수 있습니다.</p>
				</section>

				<section class="space-y-6">
					<div class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
						<div class="flex items-center gap-2"><Box size={18} class="text-primary" strokeWidth={1.8} /><Typography as="h2" variant="h2">생성 파라미터</Typography></div>
						<dl class="mt-5 space-y-4 text-sm">
							<div><dt class="text-muted-foreground">타입</dt><dd class="mt-1 font-medium">3D</dd></div>
							<div><dt class="text-muted-foreground">상태</dt><dd class="mt-1 font-medium">{statusLabel(generation.status)}</dd></div>
							<div><dt class="text-muted-foreground">품질 프리셋</dt><dd class="mt-1 font-medium">{presetLabel(generation.preset)}</dd></div>
							<div><dt class="text-muted-foreground">Seed</dt><dd class="mt-1 break-all font-medium">{generation.seed ?? '무작위'}</dd></div>
							<div><dt class="text-muted-foreground">배경 제거</dt><dd class="mt-1 font-medium">{generation.remove_background ? '사용' : '사용 안 함'}</dd></div>
							<div><dt class="text-muted-foreground">오브젝트 여백</dt><dd class="mt-1 font-medium">{generation.padding}</dd></div>
							<div><dt class="text-muted-foreground">소스 파일</dt><dd class="mt-1 break-all font-medium">{generation.source_filename}</dd></div>
							<div><dt class="text-muted-foreground">파일 용량</dt><dd class="mt-1 font-medium">{formatFileSize(generation.file_size_bytes)}</dd></div>
						</dl>
					</div>
					{#if generation.source_image_url}
						<div class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6"><Typography as="h2" variant="h2">소스 이미지</Typography><ImageMedia source={generation.source_image_url} sourceType={imageSourceType(generation.source_image_url)} alt="3D 모델 소스 이미지" class="mt-4 max-h-72" /></div>
					{/if}
				</section>
			</div>

			<section class="flex justify-end"><PrimaryButton loading={deleting} disabled={deleting} variant="destructive" onclick={() => (deleteModalOpen = true)}><Trash2 size={16} strokeWidth={2} /><span>3D 모델 삭제</span></PrimaryButton></section>
		</main>
	</div>
{:else}
	<div class="flex min-h-screen items-center justify-center bg-background px-4"><div class="text-center"><Typography as="h1" variant="h2">3D 모델을 찾을 수 없습니다.</Typography><a href="/vault?tab=3d" class="mt-4 inline-flex text-sm font-semibold text-primary hover:underline">보관함으로 돌아가기</a></div></div>
{/if}

<Modal bind:open={deleteModalOpen} title="3D 모델을 삭제하시겠습니까?" description="삭제한 3D 모델과 파일은 복구할 수 없습니다." closeOnBackdrop={!deleting}>
	<p class="text-sm leading-6 text-muted-foreground">이 3D 모델과 파일 스토리지의 원본을 삭제합니다.</p>
	{#snippet footer()}<OutlinedButton disabled={deleting} onclick={() => (deleteModalOpen = false)}>취소</OutlinedButton><PrimaryButton loading={deleting} variant="destructive" onclick={() => void deleteModel()}><Trash2 size={16} strokeWidth={2} /><span>삭제</span></PrimaryButton>{/snippet}
</Modal>

{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="3D 모델 상세 처리 실패" message={error} onclose={() => (error = '')} /></div>{/if}
