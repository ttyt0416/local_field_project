<script lang="ts">
	import { goto } from '$app/navigation';
	import { Activity, ChevronDown, LogIn, LogOut, Menu, Moon, Sun, UserRoundX } from '@lucide/svelte';
	import IconOutlinedButton from '../buttons/icon-outlined-button.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';

	type Props = {
		onMenuClick: () => void;
	};

	let { onMenuClick }: Props = $props();
	let accountMenuOpen = $state(false);

	function logout() {
		accountMenuOpen = false;
		authStore.clearSession();
		void goto('/login');
	}

</script>

<header class="sticky top-0 z-30 border-b border-border/80 bg-background/85 backdrop-blur-xl">
	<div class="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
		<div class="min-w-0">
			<p class="truncate text-xs text-muted-foreground">워크스페이스 / 개요</p>
			<p class="truncate text-sm font-semibold">미디어 생성 관리</p>
		</div>
		<div class="flex items-center gap-3">
			{#if authStore.initialized}
				{#if authStore.isAuthenticated}
					<details bind:open={accountMenuOpen} class="group relative">
						<summary class="flex cursor-pointer list-none items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
							<span class="hidden max-w-36 truncate sm:inline">{authStore.user?.username}</span>
							<ChevronDown size={14} strokeWidth={1.8} class="transition-transform group-open:rotate-180" />
						</summary>
						<div class="absolute right-0 top-full z-50 mt-2 w-48 rounded-xl border border-border bg-card p-1.5 text-card-foreground shadow-xl">
							<button type="button" class="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground" onclick={logout}>
								<LogOut size={15} strokeWidth={1.8} />
								<span>로그아웃</span>
							</button>
							<button type="button" class="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm text-destructive transition hover:bg-destructive/10">
								<UserRoundX size={15} strokeWidth={1.8} />
								<span>회원탈퇴</span>
							</button>
						</div>
					</details>
				{:else}
					<a href="/login" class="inline-flex items-center gap-2 rounded-lg border border-border px-2.5 py-2 text-xs font-medium text-foreground transition hover:border-primary/50 hover:bg-primary/10">
						<LogIn size={15} strokeWidth={1.8} />
						<span>로그인</span>
					</a>
				{/if}
			{/if}
			<div class="group relative flex items-center">
				<button
					type="button"
					class="inline-flex size-9 items-center justify-center rounded-lg border-0 bg-transparent p-0 text-success transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					aria-label="서버 연결 정상"
				>
					<Activity size={16} strokeWidth={1.8} />
				</button>
				<span class="pointer-events-none absolute right-0 top-full z-50 mt-2 hidden whitespace-nowrap rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium text-card-foreground shadow-xl group-hover:block group-focus-within:block">
					서버 연결 정상
				</span>
			</div>
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
			<IconOutlinedButton ariaLabel="메뉴 열기" class="lg:hidden" onclick={onMenuClick}>
				<Menu size={19} />
			</IconOutlinedButton>
		</div>
	</div>
</header>
