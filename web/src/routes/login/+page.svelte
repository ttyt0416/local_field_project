<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Moon, Sparkles, Sun } from '@lucide/svelte';
	import IconOutlinedButton from '../../../components/buttons/icon-outlined-button.svelte';
	import Input from '../../../components/inputs/input.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import PrimaryButton from '../../../components/buttons/primary-button.svelte';
	import Tab from '../../../components/tabs/tab.svelte';
	import Typography from '../../../components/typography/typography.svelte';
	import { APP_NAME } from '$lib/configs/constants';
	import { authStore } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';

	type Mode = 'login' | 'signup';
	const authTabs = [
		{ value: 'login', label: '로그인' },
		{ value: 'signup', label: '회원가입' }
	] as const;

	let mode = $state<Mode>('login');
	let username = $state('');
	let password = $state('');
	let busy = $state(false);
	let error = $state('');

	onMount(() => {
		let active = true;
		void authStore.initialize().then(() => {
			if (active && authStore.isAuthenticated) {
				void goto('/vault');
			}
		});
		return () => {
			active = false;
		};
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;

		busy = true;
		error = '';
		try {
			if (mode === 'login') {
				await authStore.login(username, password);
			} else {
				await authStore.signup(username, password);
			}
			await goto('/vault');
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '인증 요청에 실패했습니다.';
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head>
	<title>{mode === 'login' ? '로그인' : '회원가입'} · {APP_NAME}</title>
</svelte:head>

<div class="relative flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10 dark:bg-background">
	<div class="absolute right-4 top-4">
		<IconOutlinedButton
			ariaLabel={themeStore.isDark ? '라이트모드로 전환' : '다크모드로 전환'}
			pressed={themeStore.isDark}
			onclick={() => themeStore.toggle()}
		>
			{#if themeStore.isDark}
				<Sun size={17} strokeWidth={1.8} />
			{:else}
				<Moon size={17} strokeWidth={1.8} />
			{/if}
		</IconOutlinedButton>
	</div>
	<main class="w-full max-w-md">
		<div class="mb-8 text-center">
			<a href="/" class="inline-flex items-center gap-3 text-foreground">
				<span class="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
					<Sparkles size={20} strokeWidth={2} />
				</span>
				<span class="font-semibold tracking-tight">{APP_NAME}</span>
			</a>
		</div>

		<section class="rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8">
			<div class="mb-6">
				<Typography as="h1" variant="h2">{mode === 'login' ? '다시 오신 것을 환영합니다' : 'Local Field 시작하기'}</Typography>
				<Typography as="p" variant="muted" class="mt-2">
					{mode === 'login' ? '개인 보관함에 접속하려면 로그인해 주세요.' : '개인 보관함을 만들고 생성 결과를 관리하세요.'}
				</Typography>
			</div>

			<Tab items={authTabs} bind:value={mode} ariaLabel="인증 방식" class="mb-6" />

			<form class="space-y-5" onsubmit={submit}>
				<Input
					id="auth-username"
					label="아이디"
					type="text"
					autocomplete="username"
					placeholder="아이디를 입력해 주세요"
					bind:value={username}
					required
				/>
				<Input
					id="auth-password"
					label="비밀번호"
					type="password"
					autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
					placeholder="8자 이상 입력해 주세요"
					bind:value={password}
					required
				/>

				{#if error}
					<p class="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">{error}</p>
				{/if}

				<PrimaryButton type="submit" class="w-full" disabled={busy} loading={busy}>
					{mode === 'login' ? '로그인' : '회원가입'}
				</PrimaryButton>
			</form>

			{#if busy}
				<div class="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground" role="status">
					<LoadingSpinner size="sm" label="인증 처리 중" />
					<span>인증 처리 중입니다.</span>
				</div>
			{/if}
		</section>
	</main>
</div>
