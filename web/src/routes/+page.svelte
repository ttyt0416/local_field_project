<script lang="ts">
	import { ArrowUpRight, Boxes, Clock3, Plus, Settings2, Workflow } from '@lucide/svelte';
	import Input from '../../components/inputs/input.svelte';
	import Layout from '../../components/layouts/layout.svelte';
	import LoadingShimmer from '../../components/loadings/loading-shimmer.svelte';
	import LoadingSpinner from '../../components/loadings/loading-spinner.svelte';
	import Modal from '../../components/modals/modal.svelte';
	import OutlinedButton from '../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../components/buttons/primary-button.svelte';
	import Typography from '../../components/typography/typography.svelte';
	import { APP_NAME, SERVER_DOCS_URL } from '$lib/configs/constants';

	let createModalOpen = $state(false);
</script>

<svelte:head>
	<title>{APP_NAME}</title>
	<meta
		name="description"
		content="로컬 AI 미디어 생성 시스템을 제어하고 관리하는 Local Field"
	/>
</svelte:head>

<Layout>
	<div class="space-y-8">
		<section id="dashboard" class="grid gap-6 rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8 lg:grid-cols-[1fr_auto] lg:items-end">
			<div class="max-w-2xl">
				<Typography as="p" variant="eyebrow">Local Field workspace</Typography>
				<Typography as="h1" variant="display" class="mt-3">
					AI 미디어 생성 시스템을 한곳에서 관리합니다.
				</Typography>
				<Typography as="p" variant="muted" class="mt-5 max-w-xl text-base">
					로컬 환경의 이미지·영상·음성·3D 생성 시스템을 연결하고 생성 작업과 결과물을 관리합니다.
				</Typography>
			</div>
			<div class="flex flex-col gap-2 sm:flex-row lg:flex-col">
				<PrimaryButton onclick={() => (createModalOpen = true)}>
					<Plus size={17} strokeWidth={2} />
					<span>새 생성 작업</span>
				</PrimaryButton>
				<OutlinedButton onclick={() => window.location.assign(SERVER_DOCS_URL)}>
					<span>API 문서</span>
					<ArrowUpRight size={16} strokeWidth={1.8} />
				</OutlinedButton>
			</div>
		</section>

		<section id="systems" class="space-y-4">
			<div class="flex items-end justify-between gap-4">
				<div>
					<Typography as="h2" variant="h2">연결된 시스템</Typography>
					<Typography as="p" variant="muted" class="mt-1">현재 로컬 런타임에 연결된 생성 도구입니다.</Typography>
				</div>
				<OutlinedButton class="hidden sm:inline-flex">
					<Boxes size={16} strokeWidth={1.8} />
					<span>전체 보기</span>
				</OutlinedButton>
			</div>

			<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
				<article class="rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/40">
					<div class="flex items-start justify-between gap-4">
						<div class="flex size-11 items-center justify-center rounded-xl bg-primary/15 text-primary">
							<Workflow size={21} strokeWidth={1.8} />
						</div>
						<span class="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
							<span class="size-1.5 rounded-full bg-success"></span>
							온라인
						</span>
					</div>
					<Typography as="h3" variant="h3" class="mt-5">ComfyUI</Typography>
					<Typography as="p" variant="muted" class="mt-1">이미지 생성 워크플로</Typography>
				</article>

				<article class="rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-secondary/40">
					<div class="flex items-start justify-between gap-4">
						<div class="flex size-11 items-center justify-center rounded-xl bg-secondary/15 text-secondary">
							<Workflow size={21} strokeWidth={1.8} />
						</div>
						<span class="inline-flex items-center gap-1.5 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
							<span class="size-1.5 rounded-full bg-warning"></span>
							대기 중
						</span>
					</div>
					<Typography as="h3" variant="h3" class="mt-5">AnimateDiff</Typography>
					<Typography as="p" variant="muted" class="mt-1">영상 생성 워크플로</Typography>
				</article>

				<article class="rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-tertiary/40">
					<div class="flex items-start justify-between gap-4">
						<div class="flex size-11 items-center justify-center rounded-xl bg-tertiary/15 text-tertiary">
							<Workflow size={21} strokeWidth={1.8} />
						</div>
						<span class="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
							<span class="size-1.5 rounded-full bg-muted-foreground"></span>
							오프라인
						</span>
					</div>
					<Typography as="h3" variant="h3" class="mt-5">Audio Lab</Typography>
					<Typography as="p" variant="muted" class="mt-1">음성 생성 워크플로</Typography>
				</article>
			</div>
		</section>

		<section id="jobs" class="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
			<article class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
				<div class="flex items-center justify-between gap-4">
					<div>
						<Typography as="h2" variant="h2">최근 생성 작업</Typography>
						<Typography as="p" variant="muted" class="mt-1">최근 실행된 작업의 상태를 확인합니다.</Typography>
					</div>
					<Clock3 size={20} class="text-muted-foreground" strokeWidth={1.8} />
				</div>
				<div class="mt-6 divide-y divide-border">
					<div class="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
						<div class="min-w-0">
							<p class="truncate text-sm font-medium">제품 소개 이미지 생성</p>
							<p class="mt-1 text-xs text-muted-foreground">ComfyUI · 12분 전</p>
						</div>
						<span class="w-fit rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">완료</span>
					</div>
					<div class="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
						<div class="min-w-0">
							<p class="truncate text-sm font-medium">짧은 홍보 영상 렌더링</p>
							<p class="mt-1 text-xs text-muted-foreground">AnimateDiff · 28분 전</p>
						</div>
						<span class="inline-flex w-fit items-center gap-2 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
							<LoadingSpinner size="sm" label="렌더링 처리 중" />
							<span>처리 중</span>
						</span>
					</div>
					<div class="flex flex-col gap-3 border-t border-border py-4 sm:flex-row sm:items-center sm:justify-between">
						<div class="space-y-2">
							<LoadingShimmer class="h-3 w-44" />
							<LoadingShimmer class="h-3 w-24" />
						</div>
						<LoadingShimmer class="h-6 w-16 rounded-full" rounded />
					</div>
				</div>
			</article>

			<article id="settings" class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
				<div class="flex size-11 items-center justify-center rounded-xl bg-muted text-muted-foreground">
					<Settings2 size={21} strokeWidth={1.8} />
				</div>
				<Typography as="h2" variant="h2" class="mt-5">빠른 설정</Typography>
				<Typography as="p" variant="muted" class="mt-1">기본 생성 환경을 관리합니다.</Typography>
				<div class="mt-6 space-y-3 text-sm">
					<div class="flex items-center justify-between gap-4 rounded-xl bg-muted/60 px-4 py-3">
						<span class="text-muted-foreground">기본 모델</span>
						<span class="font-medium">SDXL</span>
					</div>
					<div class="flex items-center justify-between gap-4 rounded-xl bg-muted/60 px-4 py-3">
						<span class="text-muted-foreground">출력 형식</span>
						<span class="font-medium">PNG</span>
					</div>
				</div>
			</article>
		</section>
	</div>
</Layout>

<Modal
	bind:open={createModalOpen}
	title="새 생성 작업"
	description="연결된 시스템에서 실행할 작업의 기본 정보를 입력합니다."
>
	<div class="space-y-4">
		<Input id="job-name" label="작업 이름" placeholder="예: 제품 소개 이미지" />
		<label class="block space-y-2">
			<span class="text-sm font-medium">생성 시스템</span>
			<select class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20">
				<option>ComfyUI</option>
				<option>AnimateDiff</option>
				<option>Audio Lab</option>
			</select>
		</label>
	</div>

	{#snippet footer()}
		<OutlinedButton onclick={() => (createModalOpen = false)}>취소</OutlinedButton>
		<PrimaryButton onclick={() => (createModalOpen = false)}>작업 만들기</PrimaryButton>
	{/snippet}
</Modal>
