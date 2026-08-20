<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Archive, Image, LogOut, Video, Volume2 } from '@lucide/svelte';
	import OutlinedButton from '../../../components/buttons/outlined-button.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import Layout from '../../../components/layouts/layout.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';

	let ready = $state(false);

	onMount(() => {
		void loadVault();
	});

	async function loadVault() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		ready = true;
	}

	async function logout() {
		authStore.clearSession();
		await goto('/login');
	}
</script>

<svelte:head>
	<title>개인 보관함 · Local Field</title>
	<meta name="description" content="로그인한 사용자의 개인 AI 미디어 보관함" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<LoadingSpinner size="lg" label="개인 보관함을 불러오는 중" />
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
					<Typography as="h1" variant="display" class="mt-3">개인 보관함</Typography>
					<Typography as="p" variant="muted" class="mt-3 max-w-2xl text-base">
						{authStore.user?.email} 계정의 생성 결과와 작업 기록을 관리하는 공간입니다.
					</Typography>
				</div>
				<OutlinedButton onclick={logout}>
					<LogOut size={16} strokeWidth={1.8} />
					<span>로그아웃</span>
				</OutlinedButton>
			</section>

			<section class="grid gap-4 sm:grid-cols-3">
				<div class="rounded-2xl border border-border bg-card p-5 shadow-sm">
					<div class="flex items-center gap-3 text-muted-foreground">
						<Image size={18} strokeWidth={1.8} />
						<span class="text-sm">이미지</span>
					</div>
					<p class="mt-4 text-3xl font-semibold tracking-tight">0</p>
				</div>
				<div class="rounded-2xl border border-border bg-card p-5 shadow-sm">
					<div class="flex items-center gap-3 text-muted-foreground">
						<Video size={18} strokeWidth={1.8} />
						<span class="text-sm">영상</span>
					</div>
					<p class="mt-4 text-3xl font-semibold tracking-tight">0</p>
				</div>
				<div class="rounded-2xl border border-border bg-card p-5 shadow-sm">
					<div class="flex items-center gap-3 text-muted-foreground">
						<Volume2 size={18} strokeWidth={1.8} />
						<span class="text-sm">음성</span>
					</div>
					<p class="mt-4 text-3xl font-semibold tracking-tight">0</p>
				</div>
			</section>

			<section class="rounded-2xl border border-dashed border-border bg-card/70 p-8 text-center sm:p-12">
				<div class="mx-auto flex size-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
					<Archive size={26} strokeWidth={1.6} />
				</div>
				<Typography as="h2" variant="h2" class="mt-5">보관된 결과물이 없습니다.</Typography>
				<Typography as="p" variant="muted" class="mx-auto mt-2 max-w-md">
					새 생성 작업을 실행하면 이 계정의 개인 보관함에 결과물이 표시됩니다.
				</Typography>
			</section>
		</div>
	</Layout>
{/if}
