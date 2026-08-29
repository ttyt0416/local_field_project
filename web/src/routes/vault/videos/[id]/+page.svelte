<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { ArrowLeft, Crop, Download, Heart, Trash2, Video } from '@lucide/svelte';
	import VideoMedia from '../../../../../components/media/video.svelte';
	import VideoEditor from '../../../../../components/media/video-editor.svelte';
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
	import { formatElapsedSeconds, formatKstDateTime } from '$lib/utils/generation';

	type VaultVideoDetail = {
		id: string;
		media_type: string;
		mode: 'i2v' | 'fl2v' | 'r2v';
		fps: number;
		status: string;
		prompt: string;
		video_url: string | null;
		view_count: number;
		is_favorite: boolean;
		created_at: string;
		completed_at: string | null;
		elapsed_seconds: number;
		is_edited: boolean;
	};

	let ready = $state(false);
	let generation = $state<VaultVideoDetail | null>(null);
	let error = $state('');
	let deleteModalOpen = $state(false);
	let deleting = $state(false);
	let favoriteUpdating = $state(false);
	let downloading = $state(false);
	let videoEditorOpen = $state(false);
	let editError = $state('');

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
			error = '생성 결과 식별자가 없습니다.';
			ready = true;
			return;
		}
		try {
			generation = await apiJson<VaultVideoDetail>(`vault/videos/${generationId}`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '동영상 상세 정보를 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	async function toggleFavorite() {
		if (!generation || favoriteUpdating) return;
		favoriteUpdating = true;
		try {
			const result = await apiJson<{ is_favorite: boolean }>(`vault/videos/${generation.id}/favorite`, {
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

	async function downloadVideo() {
		if (!generation?.video_url || downloading) return;
		downloading = true;
		try {
			await downloadMedia(generation.video_url, `local-field-video-${generation.id}.mp4`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '영상을 다운로드하지 못했습니다.';
		} finally {
			downloading = false;
		}
	}

	async function deleteVideo() {
		if (!generation || deleting) return;
		deleting = true;
		try {
			await apiDelete(`vault/videos/${generation.id}`);
			deleteModalOpen = false;
			await goto('/vault?tab=videos');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '영상을 삭제하지 못했습니다.';
		} finally {
			deleting = false;
		}
	}

	function statusLabel(status: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패' }[status] ?? status;
	}
</script>

<svelte:head>
	<title>동영상 콘텐츠 상세 · Local Field</title>
	<meta name="description" content="생성된 동영상 콘텐츠 상세" />
</svelte:head>

{#if !ready}
	<div class="min-h-screen bg-muted/30 px-4 py-8 text-foreground dark:bg-background sm:px-6 lg:px-8">
		<main class="mx-auto max-w-6xl space-y-6">
			<a href="/vault?tab=videos" class="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-foreground"><ArrowLeft size={16} strokeWidth={1.8} />보관함으로 돌아가기</a>
			<section><Typography as="h1" variant="display">동영상 콘텐츠 상세</Typography><div class="flex min-h-[24rem] items-center justify-center"><LoadingSpinner size="lg" label="동영상 상세 정보를 불러오는 중" /></div></section>
		</main>
	</div>
{:else if generation}
	<div class="min-h-screen bg-muted/30 px-4 py-8 text-foreground dark:bg-background sm:px-6 lg:px-8">
		<main class="mx-auto max-w-6xl space-y-6">
			<a href="/vault?tab=videos" class="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-foreground"><ArrowLeft size={16} strokeWidth={1.8} />보관함으로 돌아가기</a>
			<section>
				<Typography as="h1" variant="display">동영상 콘텐츠 상세</Typography>
				{#if generation.is_edited}<span class="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">편집 결과</span>{/if}
				<p class="mt-3 text-sm text-muted-foreground">생성 시작 {formatKstDateTime(generation.created_at)} · 소요 {formatElapsedSeconds(generation.elapsed_seconds)} · 조회 {generation.view_count}</p>
			</section>

			<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<div class="relative overflow-hidden rounded-xl bg-black">
						{#if generation.video_url}
							<VideoMedia source={generation.video_url} sourceType="server" preview={false} muted={false} class="min-h-[24rem] sm:min-h-[36rem]" />
						{:else}
							<div class="flex min-h-[24rem] items-center justify-center bg-muted text-sm text-muted-foreground">영상 결과가 아직 없습니다.</div>
						{/if}
						<div class="absolute bottom-3 right-3 z-10 flex gap-2">
							<IconOutlinedButton ariaLabel="영상 다운로드" loading={downloading} disabled={!generation.video_url} class="bg-card/90 shadow-lg" onclick={() => void downloadVideo()}><Download size={18} strokeWidth={1.9} /></IconOutlinedButton>
							<IconOutlinedButton variant="filled" ariaLabel={generation.is_favorite ? '즐겨찾기 해제' : '즐겨찾기 추가'} pressed={generation.is_favorite} loading={favoriteUpdating} class={generation.is_favorite ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-card/90'} onclick={() => void toggleFavorite()}><Heart size={18} strokeWidth={1.9} fill={generation.is_favorite ? 'currentColor' : 'none'} /></IconOutlinedButton>
						</div>
					</div>
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<div class="flex items-center gap-2"><Video size={18} class="text-primary" strokeWidth={1.8} /><Typography as="h2" variant="h2">생성 파라미터</Typography></div>
					<dl class="mt-5 space-y-4 text-sm">
						<div><dt class="text-muted-foreground">타입</dt><dd class="mt-1 font-medium">{generation.media_type}</dd></div>
						<div><dt class="text-muted-foreground">생성 방식</dt><dd class="mt-1 font-medium">{generation.mode.toUpperCase()}</dd></div>
						<div><dt class="text-muted-foreground">상태</dt><dd class="mt-1 font-medium">{statusLabel(generation.status)}</dd></div>
						<div><dt class="text-muted-foreground">FPS</dt><dd class="mt-1 font-medium">{generation.fps}</dd></div>
					</dl>
				</section>
			</div>

			<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
				<Typography as="h2" variant="h2">생성 프롬프트</Typography>
				<p class="mt-4 whitespace-pre-wrap rounded-xl bg-muted/60 p-4 text-sm leading-6">{generation.prompt}</p>
			</section>

			<section class="flex flex-wrap justify-end gap-3">
				<OutlinedButton disabled={!generation.video_url} onclick={() => (videoEditorOpen = true)}><Crop size={16} strokeWidth={1.9} /><span>동영상 편집</span></OutlinedButton>
				<PrimaryButton loading={deleting} disabled={deleting} variant="destructive" onclick={() => (deleteModalOpen = true)}><Trash2 size={16} strokeWidth={2} /><span>콘텐츠 삭제</span></PrimaryButton>
			</section>
		</main>
	</div>
{:else}
	<div class="flex min-h-screen items-center justify-center bg-background px-4"><div class="text-center"><Typography as="h1" variant="h2">동영상 콘텐츠를 찾을 수 없습니다.</Typography><a href="/vault?tab=videos" class="mt-4 inline-flex text-sm font-semibold text-primary hover:underline">보관함으로 돌아가기</a></div></div>
{/if}

<Modal bind:open={deleteModalOpen} title="영상을 삭제하시겠습니까?" description="삭제한 영상과 파일은 복구할 수 없습니다." closeOnBackdrop={!deleting}>
	<p class="text-sm leading-6 text-muted-foreground">이 영상과 파일 스토리지의 원본을 삭제합니다.</p>
	{#snippet footer()}<OutlinedButton disabled={deleting} onclick={() => (deleteModalOpen = false)}>취소</OutlinedButton><PrimaryButton loading={deleting} variant="destructive" onclick={() => void deleteVideo()}><Trash2 size={16} strokeWidth={2} /><span>삭제</span></PrimaryButton>{/snippet}
</Modal>

{#if generation}
	<VideoEditor
		bind:open={videoEditorOpen}
		generationId={page.params.id ?? ''}
		videoUrl={generation.video_url ?? ''}
		onsaved={(generationId) => void goto(`/vault/videos/${generationId}`)}
		onerror={(message) => (editError = message)}
	/>
{/if}

{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="동영상 상세 처리 실패" message={error} onclose={() => (error = '')} /></div>
{:else if editError}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="편집 실패" message={editError} onclose={() => (editError = '')} /></div>{/if}
