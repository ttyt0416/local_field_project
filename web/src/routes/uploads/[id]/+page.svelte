<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { ArrowLeft, AudioLines, Crop, Download, Image as ImageIcon, Trash2, Video } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import ImageEditor from '../../../../components/media/image-editor.svelte';
	import VideoMedia from '../../../../components/media/video.svelte';
	import VideoEditor from '../../../../components/media/video-editor.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Modal from '../../../../components/modals/modal.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';
	import { formatElapsedSeconds, formatFileSize, formatKstDateTime } from '$lib/utils/generation';
	import { downloadMedia } from '$lib/utils/download';

	type MediaAssetDetail = {
		file_id: string;
		filename: string;
		content_type: string;
		media_kind: 'image' | 'audio' | 'video';
		source_type: string;
		url: string | null;
		created_at: string;
		size: number;
		duration_seconds: number | null;
		width: number | null;
		height: number | null;
	};

	let ready = $state(false);
	let asset = $state<MediaAssetDetail | null>(null);
	let error = $state('');
	let editError = $state('');
	let deleteModalOpen = $state(false);
	let deleting = $state(false);
	let downloading = $state(false);
	let imageEditorOpen = $state(false);
	let videoEditorOpen = $state(false);

	onMount(() => {
		void loadDetail();
	});

	async function loadDetail() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		const fileId = page.params.id;
		if (!fileId) {
			error = '업로드 콘텐츠 식별자가 없습니다.';
			ready = true;
			return;
		}
		try {
			asset = await apiJson<MediaAssetDetail>(`uploads/${encodeURIComponent(fileId)}`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '업로드 콘텐츠 상세 정보를 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	async function downloadAsset() {
		if (!asset?.url || downloading) return;
		downloading = true;
		try {
			await downloadMedia(asset.url, asset.filename);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '콘텐츠를 다운로드하지 못했습니다.';
		} finally {
			downloading = false;
		}
	}

	async function deleteAsset() {
		if (!asset || deleting) return;
		deleting = true;
		try {
			await apiDelete(`uploads/${encodeURIComponent(asset.file_id)}`);
			deleteModalOpen = false;
			await goto('/uploads');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '업로드 콘텐츠를 삭제하지 못했습니다.';
		} finally {
			deleting = false;
		}
	}

	function sourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function sourcePath() {
		return `uploads/${encodeURIComponent(asset?.file_id ?? '')}/source`;
	}

	function editPath(kind: 'image' | 'video') {
		return `uploads/${encodeURIComponent(asset?.file_id ?? '')}/edit${kind === 'video' ? '/video' : ''}`;
	}

	function sourceLabel() {
		return asset?.source_type === 'edited_upload' ? '편집 결과' : '업로드 콘텐츠';
	}
</script>

<svelte:head>
	<title>업로드 콘텐츠 상세 · Local Field</title>
	<meta name="description" content="업로드한 이미지와 동영상의 상세 정보 및 편집" />
</svelte:head>

{#if !ready}
	<div class="min-h-screen bg-muted/30 px-4 py-8 text-foreground dark:bg-background sm:px-6 lg:px-8">
		<main class="mx-auto max-w-6xl space-y-6">
			<a href="/uploads" class="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-foreground"><ArrowLeft size={16} strokeWidth={1.8} />업로드 콘텐츠로 돌아가기</a>
			<section><Typography as="h1" variant="display">업로드 콘텐츠 상세</Typography><div class="flex min-h-[24rem] items-center justify-center"><LoadingSpinner size="lg" label="업로드 콘텐츠 상세 정보를 불러오는 중" /></div></section>
		</main>
	</div>
{:else if asset}
	<div class="min-h-screen bg-muted/30 px-4 py-8 text-foreground dark:bg-background sm:px-6 lg:px-8">
		<main class="mx-auto max-w-6xl space-y-6">
			<a href="/uploads" class="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-foreground"><ArrowLeft size={16} strokeWidth={1.8} />업로드 콘텐츠로 돌아가기</a>
			<section>
				<Typography as="h1" variant="display">업로드 콘텐츠 상세</Typography>
				<p class="mt-3 break-all text-sm text-muted-foreground">{sourceLabel()} · {formatKstDateTime(asset.created_at)} · 용량 {formatFileSize(asset.size)}{#if asset.duration_seconds !== null} · 재생 시간 {formatElapsedSeconds(asset.duration_seconds)}{/if}</p>
			</section>

			<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<div class="relative overflow-hidden rounded-xl bg-black">
						{#if asset.url && asset.media_kind === 'image'}
							<ImageMedia source={asset.url} sourceType={sourceType(asset.url)} alt={asset.filename} class="min-h-[24rem] sm:min-h-[36rem]" />
						{:else if asset.url && asset.media_kind === 'video'}
							<VideoMedia source={asset.url} sourceType="server" preview={false} muted={false} class="min-h-[24rem] sm:min-h-[36rem]" />
						{:else if asset.url && asset.media_kind === 'audio'}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-5 p-6"><AudioLines size={48} class="text-primary" /><audio src={asset.url} controls class="w-full"></audio></div>
						{:else}
							<div class="flex min-h-[24rem] items-center justify-center text-sm text-muted-foreground">미리보기를 사용할 수 없습니다.</div>
						{/if}
						<div class="absolute bottom-3 right-3 z-10 flex gap-2">
							<IconOutlinedButton ariaLabel="콘텐츠 다운로드" loading={downloading} disabled={!asset.url} class="bg-card/90 shadow-lg" onclick={() => void downloadAsset()}><Download size={18} strokeWidth={1.9} /></IconOutlinedButton>
						</div>
					</div>
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<div class="flex items-center gap-2">
						{#if asset.media_kind === 'image'}<ImageIcon size={18} class="text-primary" strokeWidth={1.8} />{:else if asset.media_kind === 'video'}<Video size={18} class="text-primary" strokeWidth={1.8} />{:else}<AudioLines size={18} class="text-primary" strokeWidth={1.8} />{/if}
						<Typography as="h2" variant="h2">파일 정보</Typography>
					</div>
					<dl class="mt-5 space-y-4 text-sm">
						<div><dt class="text-muted-foreground">파일 이름</dt><dd class="mt-1 break-all font-medium">{asset.filename}</dd></div>
						<div><dt class="text-muted-foreground">종류</dt><dd class="mt-1 font-medium">{asset.media_kind.toUpperCase()}</dd></div>
						<div><dt class="text-muted-foreground">파일 용량</dt><dd class="mt-1 font-medium">{formatFileSize(asset.size)}</dd></div>
						{#if asset.width && asset.height}<div><dt class="text-muted-foreground">크기</dt><dd class="mt-1 font-medium">{asset.width} × {asset.height}</dd></div>{/if}
						{#if asset.duration_seconds !== null}<div><dt class="text-muted-foreground">재생 시간</dt><dd class="mt-1 font-medium">{formatElapsedSeconds(asset.duration_seconds)}</dd></div>{/if}
					</dl>
				</section>
			</div>

			<section class="flex flex-col justify-end gap-3 sm:flex-row">
				{#if asset.media_kind === 'image'}<OutlinedButton disabled={!asset.url} onclick={() => (imageEditorOpen = true)}><Crop size={16} strokeWidth={1.9} /><span>이미지 편집</span></OutlinedButton>{:else if asset.media_kind === 'video'}<OutlinedButton disabled={!asset.url} onclick={() => (videoEditorOpen = true)}><Crop size={16} strokeWidth={1.9} /><span>동영상 편집</span></OutlinedButton>{/if}
				<PrimaryButton loading={deleting} disabled={deleting} variant="destructive" onclick={() => (deleteModalOpen = true)}><Trash2 size={16} strokeWidth={2} /><span>콘텐츠 삭제</span></PrimaryButton>
			</section>
		</main>
	</div>
{:else}
	<div class="flex min-h-screen items-center justify-center bg-background px-4"><div class="text-center"><Typography as="h1" variant="h2">업로드 콘텐츠를 찾을 수 없습니다.</Typography><a href="/uploads" class="mt-4 inline-flex text-sm font-semibold text-primary hover:underline">업로드 콘텐츠로 돌아가기</a></div></div>
{/if}

<Modal bind:open={deleteModalOpen} title="업로드 콘텐츠를 삭제하시겠습니까?" description="삭제한 콘텐츠와 파일은 복구할 수 없습니다." closeOnBackdrop={!deleting}>
	<p class="text-sm leading-6 text-muted-foreground">'{asset?.filename}' 콘텐츠와 파일 스토리지 원본을 함께 삭제합니다.</p>
	{#snippet footer()}<OutlinedButton disabled={deleting} onclick={() => (deleteModalOpen = false)}>취소</OutlinedButton><PrimaryButton loading={deleting} variant="destructive" onclick={() => void deleteAsset()}><Trash2 size={16} strokeWidth={2} /><span>삭제</span></PrimaryButton>{/snippet}
</Modal>

{#if asset?.media_kind === 'image'}
	<ImageEditor bind:open={imageEditorOpen} generationId={asset.file_id} sourcePath={sourcePath()} editPath={editPath('image')} onsaved={(fileId) => void goto(`/uploads/${encodeURIComponent(fileId)}`)} onerror={(message) => (editError = message)} />
{:else if asset?.media_kind === 'video'}
	<VideoEditor bind:open={videoEditorOpen} generationId={asset.file_id} videoUrl={asset.url ?? ''} editPath={editPath('video')} onsaved={(fileId) => void goto(`/uploads/${encodeURIComponent(fileId)}`)} onerror={(message) => (editError = message)} />
{/if}

{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="업로드 콘텐츠 처리 실패" message={error} onclose={() => (error = '')} /></div>{:else if editError}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="편집 실패" message={editError} onclose={() => (editError = '')} /></div>{/if}
