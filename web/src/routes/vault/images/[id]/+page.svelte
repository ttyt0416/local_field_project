<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { ArrowLeft, FileImage, Heart, SlidersHorizontal, Sparkles, Trash2 } from '@lucide/svelte';
	import ImageMedia from '../../../../../components/media/image.svelte';
	import LoadingSpinner from '../../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../../components/buttons/outlined-button.svelte';
	import IconOutlinedButton from '../../../../../components/buttons/icon-outlined-button.svelte';
	import PrimaryButton from '../../../../../components/buttons/primary-button.svelte';
	import Toast from '../../../../../components/feedback/toast.svelte';
	import Modal from '../../../../../components/modals/modal.svelte';
	import Typography from '../../../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { imageGenerationStore } from '$lib/stores/image-generation.svelte';
	import { apiDelete, apiJson } from '$lib/utils/api';

	type VaultImageDetail = {
		id: string;
		media_type: string;
		status: string;
		prompt_id: string;
		prompt: string;
		negative_prompt: string;
		checkpoint: string;
		loras: { name: string; strength: number }[];
		cfg: number;
		steps: number;
		width: number;
		height: number;
		seed: number;
		filename: string | null;
		subfolder: string;
		image_type: string;
		image_url: string | null;
		created_at: string;
		completed_at: string | null;
		view_count: number;
		is_favorite: boolean;
	};

	let ready = $state(false);
	let generation = $state<VaultImageDetail | null>(null);
	let error = $state('');
	let deleteModalOpen = $state(false);
	let deleting = $state(false);
	let favoriteUpdating = $state(false);

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
			generation = await apiJson<VaultImageDetail>(`vault/images/${generationId}`);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '생성 상세 정보를 불러오지 못했습니다.';
		} finally {
			ready = true;
		}
	}

	function requestDelete() {
		deleteModalOpen = true;
	}

	function cancelDelete() {
		deleteModalOpen = false;
	}

	async function toggleFavorite() {
		if (!generation || favoriteUpdating) return;
		favoriteUpdating = true;
		try {
			const result = await apiJson<{ is_favorite: boolean }>(`vault/images/${generation.id}/favorite`, {
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

	async function generateFromParameters() {
		if (!generation) return;
		imageGenerationStore.set({
			prompt: generation.prompt,
			negative_prompt: generation.negative_prompt,
			checkpoint: generation.checkpoint,
			cfg: generation.cfg,
			steps: generation.steps,
			width: generation.width,
			height: generation.height,
			seed: String(generation.seed),
			loras: generation.loras.map(({ name, strength }) => ({ name, strength }))
		});
		try {
			await goto('/generate/image');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '이미지 생성 페이지로 이동하지 못했습니다.';
		}
	}

	async function deleteImage() {
		const generationId = page.params.id;
		if (!generationId || deleting) return;
		deleting = true;
		try {
			await apiDelete(`vault/images/${generationId}`);
			deleteModalOpen = false;
			await goto('/vault');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '이미지를 삭제하지 못했습니다.';
		} finally {
			deleting = false;
		}
	}

	function imageSource(image: VaultImageDetail) {
		return image.image_url ?? '';
	}

	function imageSourceType(url: string): 'server' | 'external' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function statusLabel(status: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패' }[status] ?? status;
	}
</script>

<svelte:head>
	<title>이미지 상세 · Local Field</title>
	<meta name="description" content="개인 이미지 생성 결과와 사용된 파라미터 상세" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="생성 상세 정보를 불러오는 중" />
	</div>
{:else if generation}
	<div class="min-h-screen bg-muted/30 px-4 py-8 text-foreground dark:bg-background sm:px-6 lg:px-8">
		<main class="mx-auto max-w-6xl space-y-6">
			<a href="/vault" class="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-foreground">
				<ArrowLeft size={16} strokeWidth={1.8} />
				보관함으로 돌아가기
			</a>

			<section class="rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8">
				<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
					<div>
						<Typography as="p" variant="eyebrow">{generation.media_type} · {statusLabel(generation.status)}</Typography>
						<Typography as="h1" variant="display" class="mt-3">이미지 상세</Typography>
						<p class="mt-3 text-sm text-muted-foreground">조회 {generation.view_count}</p>
					</div>
					<div class="flex items-start gap-3">
						<IconOutlinedButton
							ariaLabel={generation.is_favorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
							pressed={generation.is_favorite}
							loading={favoriteUpdating}
							class={generation.is_favorite ? 'border-primary bg-primary/10 text-primary' : ''}
							onclick={() => void toggleFavorite()}
						>
							<Heart size={18} strokeWidth={1.9} fill={generation.is_favorite ? 'currentColor' : 'none'} />
						</IconOutlinedButton>
						<FileImage size={28} class="text-primary" strokeWidth={1.7} />
					</div>
				</div>
			</section>

			<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					{#if generation.image_url}
						<ImageMedia source={imageSource(generation)} sourceType={imageSourceType(imageSource(generation))} alt="생성 이미지" class="min-h-[24rem] sm:min-h-[36rem]" />
					{:else}
						<div class="flex min-h-[24rem] items-center justify-center rounded-xl bg-muted text-sm text-muted-foreground">이미지 결과가 아직 없습니다.</div>
					{/if}
					<p class="mt-3 text-xs text-muted-foreground">이미지를 클릭하거나 터치하면 크게 볼 수 있습니다.</p>
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<div class="flex items-center gap-2">
						<SlidersHorizontal size={18} class="text-primary" strokeWidth={1.8} />
						<Typography as="h2" variant="h2">생성 파라미터</Typography>
					</div>
					<dl class="mt-5 space-y-4 text-sm">
						<div><dt class="text-muted-foreground">타입</dt><dd class="mt-1 font-medium">{generation.media_type}</dd></div>
						<div><dt class="text-muted-foreground">체크포인트</dt><dd class="mt-1 break-all font-medium">{generation.checkpoint}</dd></div>
						<div>
							<dt class="text-muted-foreground">LoRA</dt>
							{#if generation.loras.length > 0}
								<dd class="mt-1 space-y-1 font-medium">
									{#each generation.loras as lora (lora.name)}
										<div class="break-all">{lora.name} / {lora.strength}</div>
									{/each}
								</dd>
							{:else}
								<dd class="mt-1 font-medium">사용 안 함</dd>
							{/if}
						</div>
						<div><dt class="text-muted-foreground">CFG / Steps</dt><dd class="mt-1 font-medium">{generation.cfg} / {generation.steps}</dd></div>
						<div><dt class="text-muted-foreground">이미지 크기</dt><dd class="mt-1 font-medium">{generation.width} × {generation.height}</dd></div>
						<div><dt class="text-muted-foreground">Seed</dt><dd class="mt-1 break-all font-medium">{generation.seed}</dd></div>
					</dl>
				</section>
			</div>

			<section class="grid gap-6 lg:grid-cols-2">
				<div class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<Typography as="h2" variant="h2">사용된 긍정 프롬프트</Typography>
					<p class="mt-4 whitespace-pre-wrap rounded-xl bg-muted/60 p-4 text-sm leading-6">{generation.prompt}</p>
				</div>
				<div class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
					<Typography as="h2" variant="h2">부정 프롬프트</Typography>
					<p class="mt-4 whitespace-pre-wrap rounded-xl bg-muted/60 p-4 text-sm leading-6">{generation.negative_prompt}</p>
				</div>
			</section>

			<section class="flex flex-col justify-end gap-3 sm:flex-row">
				<PrimaryButton onclick={() => void generateFromParameters()}>
					<Sparkles size={16} strokeWidth={1.9} />
					<span>이 설정으로 다시 생성</span>
				</PrimaryButton>
				<PrimaryButton
					loading={deleting}
					disabled={deleting}
					variant="destructive"
					onclick={requestDelete}
				>
					<Trash2 size={16} strokeWidth={2} />
					<span>이미지 삭제</span>
				</PrimaryButton>
			</section>
		</main>
	</div>
{:else}
	<div class="flex min-h-screen items-center justify-center bg-background px-4">
		<div class="text-center">
			<Typography as="h1" variant="h2">생성 결과를 찾을 수 없습니다.</Typography>
			<a href="/vault" class="mt-4 inline-flex text-sm font-semibold text-primary hover:underline">보관함으로 돌아가기</a>
		</div>
	</div>
{/if}

<Modal
	bind:open={deleteModalOpen}
	title="이미지를 삭제하시겠습니까?"
	description="삭제한 이미지는 복구할 수 없습니다."
	closeOnBackdrop={!deleting}
	onclose={cancelDelete}
>
	<p class="text-sm leading-6 text-muted-foreground">이 이미지와 파일 스토리지의 원본을 삭제합니다.</p>
	{#snippet footer()}
		<OutlinedButton disabled={deleting} onclick={cancelDelete}>취소</OutlinedButton>
		<PrimaryButton
			loading={deleting}
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
		<Toast state="negative" title="상세 조회 실패" message={error} onclose={() => (error = '')} />
	</div>
{/if}
