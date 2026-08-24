<script lang="ts">
	import { Activity, Archive, LogIn, Menu, Moon, Sun } from '@lucide/svelte';
	import IconOutlinedButton from '../buttons/icon-outlined-button.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';

	type Props = {
		onMenuClick: () => void;
	};

	let { onMenuClick }: Props = $props();
</script>

<header class="sticky top-0 z-30 border-b border-border/80 bg-background/85 backdrop-blur-xl">
	<div class="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
		<div class="min-w-0">
			<p class="truncate text-xs text-muted-foreground">워크스페이스 / 개요</p>
			<p class="truncate text-sm font-semibold">미디어 생성 관리</p>
		</div>
		<div class="flex items-center gap-3">
			<div class="hidden items-center gap-2 sm:flex">
				<Activity size={16} class="text-success" strokeWidth={1.8} />
				<span class="text-xs font-medium text-muted-foreground">로컬 연결 정상</span>
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
			{#if authStore.initialized}
				{#if authStore.isAuthenticated}
					<a href="/vault" class="inline-flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground">
						<Archive size={15} strokeWidth={1.8} />
						<span class="hidden max-w-36 truncate sm:inline">{authStore.user?.username}</span>
					</a>
				{:else}
					<a href="/login" class="inline-flex items-center gap-2 rounded-lg border border-border px-2.5 py-2 text-xs font-medium text-foreground transition hover:border-primary/50 hover:bg-primary/10">
						<LogIn size={15} strokeWidth={1.8} />
						<span>로그인</span>
					</a>
				{/if}
			{/if}
			<IconOutlinedButton ariaLabel="메뉴 열기" class="lg:hidden" onclick={onMenuClick}>
				<Menu size={19} />
			</IconOutlinedButton>
		</div>
	</div>
</header>
