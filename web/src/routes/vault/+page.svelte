<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Archive, LogOut, Trash2 } from '@lucide/svelte';
	import ImageMedia from '../../../components/media/image.svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import Modal from '../../../components/modals/modal.svelte';
	import Toast from '../../../components/feedback/toast.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import { SERVER_URL } from '$lib/configs/constants';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';

	type VaultImage = {
		id: string;
		media_type: string;
		status: string;
		checkpoint: string;
		image_url: string | null;
		created_at: string;
		completed_at: string | null;
	};

	let ready = $state(false);
	let images = $state<VaultImage[]>([]);
	let error = $state('');
	let deleteTarget = $state<VaultImage | null>(null);
	let deleteModalOpen = $state(false);
	let deletingId = $state('');

	onMount(() => {
		void loadVault();
	});

	async function loadVault() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			images = await apiJson<VaultImage[]>('vault/images');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '보관함을 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	async function logout() {
		authStore.clearSession();
		await goto('/login');
	}

	function requestDelete(image: VaultImage) {
		deleteTarget = image;
		deleteModalOpen = true;
	}

	function cancelDelete() {
		deleteModalOpen = false;
		deleteTarget = null;
	}

	async function deleteImage() {
		const target = deleteTarget;
		if (!target || deletingId) return;
		deletingId = target.id;
		try {
			await apiDelete(`vault/images/${target.id}`);
			images = images.filter((image) => image.id !== target.id);
			deleteModalOpen = false;
			deleteTarget = null;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '이미지를 삭제하지 못했습니다.';
		} finally {
			deletingId = '';
		}
	}

	function imageSource(image: VaultImage) {
		return image.image_url ? new URL(image.image_url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString() : '';
	}

	function imageSourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function statusLabel(status: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패' }[status] ?? status;
	}
</script>

<svelte:head>
	<title>보관함 · Local Field</title>
	<meta name="description" content="로그인한 사용자의 개인 AI 미디어 보관함" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="보관함을 불러오는 중" />
	</div>
{:else}
	<Layout>
		<div class="space-y-8">
			<section class="flex flex-col gap-5 rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8 md:flex-row md:items-end md:justify-between">
				<div>
					<div class="mb-4 flex size-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
						<Archive size={24} strokeWidth={1.8} />
					</div>
					<Typography as="p" variant="eyebrow">Personal workspace</Typography>
					<Typography as="h1" variant="display" class="mt-3">보관함</Typography>
					<Typography as="p" variant="muted" class="mt-3 max-w-2xl text-base">
						{authStore.user?.username} 계정의 이미지 생성 결과와 작업 기록입니다.
					</Typography>
				</div>
				<OutlinedButton onclick={logout}>
					<LogOut size={16} strokeWidth={1.8} />
					<span>로그아웃</span>
				</OutlinedButton>
			</section>

			<section class="flex items-center justify-between rounded-2xl border border-border bg-card p-5 shadow-sm">
				<div>
					<p class="text-sm text-muted-foreground">이미지 생성</p>
					<p class="mt-2 text-3xl font-semibold tracking-tight">{images.length}</p>
				</div>
				<Archive size={24} class="text-primary" strokeWidth={1.8} />
			</section>

			{#if images.length === 0}
				<section class="rounded-2xl border border-dashed border-border bg-card/70 p-8 text-center sm:p-12">
					<div class="mx-auto flex size-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
						<Archive size={26} strokeWidth={1.6} />
					</div>
					<Typography as="h2" variant="h2" class="mt-5">보관된 이미지가 없습니다.</Typography>
					<Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">
						이미지를 생성하면 이 계정의 결과만 이 보관함에 표시됩니다.
					</Typography>
				</section>
			{:else}
				<section class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
					{#each images as image (image.id)}
						<article class="relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition hover:border-primary/40 hover:shadow-md">
							<a
								href={`/vault/images/${image.id}`}
								aria-label={`${image.checkpoint} 이미지 상세 보기`}
								class="absolute inset-0 z-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							></a>
							<div class="pointer-events-none relative z-10">
							<div class="relative">
								{#if image.image_url}
									<ImageMedia source={imageSource(image)} sourceType={imageSourceType(imageSource(image))} alt="생성 이미지" class="aspect-square" />
								{:else}
									<div class="flex aspect-square items-center justify-center bg-muted text-sm text-muted-foreground">이미지 준비 중</div>
								{/if}
								<IconOutlinedButton
									ariaLabel="이미지 삭제"
									loading={deletingId === image.id}
									variant="destructive"
									class="pointer-events-auto absolute bottom-3 right-3 z-10 shadow-lg"
									onclick={() => requestDelete(image)}
								>
									<Trash2 size={17} strokeWidth={2} />
								</IconOutlinedButton>
							</div>
							<div class="space-y-3 p-4">
								<div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
									<span>{image.media_type} · {statusLabel(image.status)}</span>
									<span>{new Date(image.created_at).toLocaleDateString('ko-KR')}</span>
								</div>
								<p class="truncate text-xs text-muted-foreground">{image.checkpoint}</p>
							</div>
						</div>
						</article>
					{/each}
				</section>
			{/if}
		</div>
	</Layout>

	<Modal
		bind:open={deleteModalOpen}
		title="이미지를 삭제하시겠습니까?"
		description="삭제한 이미지는 복구할 수 없습니다."
		closeOnBackdrop={!deletingId}
		onclose={cancelDelete}
	>
		<p class="text-sm leading-6 text-muted-foreground">선택한 이미지를 보관함과 파일 스토리지에서 삭제합니다.</p>
		{#snippet footer()}
			<OutlinedButton disabled={Boolean(deletingId)} onclick={cancelDelete}>취소</OutlinedButton>
			<PrimaryButton
				loading={Boolean(deletingId)}
				variant="destructive"
				onclick={() => void deleteImage()}
			>
				<Trash2 size={16} strokeWidth={2} />
				<span>삭제</span>
			</PrimaryButton>
		{/snippet}
	</Modal>

	{#if error}
		<div class="fixed right-4 top-4 z-50">
			<Toast state="negative" title="보관함 조회 실패" message={error} onclose={() => (error = '')} />
		</div>
	{/if}
{/if}
