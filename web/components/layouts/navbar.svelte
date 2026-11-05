<script lang="ts">
	import { onMount } from 'svelte';
	import { Activity, Menu, Moon, Sun } from '@lucide/svelte';
	import { apiJson } from '$lib/utils/api';
	import IconOutlinedButton from '../buttons/icon-outlined-button.svelte';
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

	let { onMenuClick }: Props = $props();
	let hardwareMetrics = $state<HardwareMetrics | null>(null);

	async function refreshHardwareMetrics() {
		try {
			hardwareMetrics = await apiJson<HardwareMetrics>('hardware/metrics', { timeout: 4_000 });
		} catch {
			hardwareMetrics = null;
		}
	}

	function displayPercent(value: number) {
		return `${Math.round(value)}%`;
	}


	onMount(() => {
		void refreshHardwareMetrics();
		const interval = window.setInterval(() => void refreshHardwareMetrics(), 5_000);
		return () => window.clearInterval(interval);
	});

</script>

<header class="sticky top-0 z-30 border-b border-border/80 bg-background/85 backdrop-blur-xl">
	<div class="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
		<div class="flex min-w-0 items-center gap-3">
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
