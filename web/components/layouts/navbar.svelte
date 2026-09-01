<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Activity, ChevronDown, LogIn, LogOut, Menu, Moon, Sun, UserRoundX } from '@lucide/svelte';
	import { apiJson } from '$lib/utils/api';
	import IconOutlinedButton from '../buttons/icon-outlined-button.svelte';
	import Toast from '../feedback/toast.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';

	type Props = {
		onMenuClick: () => void;
	};

	type HardwareMetrics = {
		cpu_percent: number;
		gpu_percent: number;
		ram_percent: number;
		disk_percent: number;
	};

	type ToastData = {
		title: string;
		message: string;
	};

	let { onMenuClick }: Props = $props();
	let accountMenuOpen = $state(false);
	let hardwareMetrics = $state<HardwareMetrics | null>(null);
	let monitorToast = $state<ToastData | null>(null);
	let monitorRequestFailed = $state(false);

	async function refreshHardwareMetrics() {
		if (!authStore.isAuthenticated) {
			hardwareMetrics = null;
			monitorRequestFailed = false;
			return;
		}
		try {
			hardwareMetrics = await apiJson<HardwareMetrics>('hardware/metrics', { timeout: 4_000 });
			monitorRequestFailed = false;
		} catch (error) {
			hardwareMetrics = null;
			if (!monitorRequestFailed) {
				monitorRequestFailed = true;
				monitorToast = {
					title: '하드웨어 모니터 연결 실패',
					message: error instanceof Error ? error.message : '서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'
				};
			}
		}
	}

	function displayPercent(value: number) {
		return `${Math.round(value)}%`;
	}

	$effect(() => {
		if (authStore.isAuthenticated) void refreshHardwareMetrics();
		else {
			hardwareMetrics = null;
			monitorRequestFailed = false;
		}
	});

	onMount(() => {
		const interval = window.setInterval(() => void refreshHardwareMetrics(), 5_000);
		return () => window.clearInterval(interval);
	});

	function logout() {
		accountMenuOpen = false;
		authStore.clearSession();
		void goto('/login');
	}
</script>

<header class="sticky top-0 z-30 border-b border-border/80 bg-background/85 backdrop-blur-xl">
	<div class="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
		<div class="flex min-w-0 items-center gap-3">
			{#if authStore.initialized}
				{#if authStore.isAuthenticated}
					<details bind:open={accountMenuOpen} class="group relative">
						<summary class="flex cursor-pointer list-none items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
							<span class="hidden max-w-36 truncate sm:inline">{authStore.user?.username}</span>
							<ChevronDown size={14} strokeWidth={1.8} class="transition-transform group-open:rotate-180" />
						</summary>
						<div class="absolute left-0 top-full z-50 mt-2 w-48 rounded-xl border border-border bg-card p-1.5 text-card-foreground shadow-xl">
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
		{#if hardwareMetrics}
			<div
				class="shrink-0 rounded-lg border border-border bg-muted/40 px-2 py-1"
				aria-label={`CPU ${displayPercent(hardwareMetrics.cpu_percent)}, GPU ${displayPercent(hardwareMetrics.gpu_percent)}, RAM ${displayPercent(hardwareMetrics.ram_percent)}, DISK ${displayPercent(hardwareMetrics.disk_percent)}`}
			>
				<div class="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] leading-4 text-muted-foreground">
					<span><strong class="mr-1 text-foreground">CPU</strong>{displayPercent(hardwareMetrics.cpu_percent)}</span>
					<span><strong class="mr-1 text-foreground">GPU</strong>{displayPercent(hardwareMetrics.gpu_percent)}</span>
					<span><strong class="mr-1 text-foreground">RAM</strong>{displayPercent(hardwareMetrics.ram_percent)}</span>
					<span><strong class="mr-1 text-foreground">DISK</strong>{displayPercent(hardwareMetrics.disk_percent)}</span>
				</div>
			</div>
		{/if}
	</div>
</header>

{#if monitorToast}
	<div class="fixed right-4 top-4 z-50">
		<Toast state="negative" title={monitorToast.title} message={monitorToast.message} onclose={() => (monitorToast = null)} />
	</div>
{/if}
