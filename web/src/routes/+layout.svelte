<script lang="ts">
	import { browser } from '$app/environment';
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
	import { trackWebEvent } from '$lib/utils/api';
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();

	function currentPath() {
		return `${window.location.pathname}${window.location.search}`;
	}

	function targetLabel(element: HTMLElement) {
		return element.getAttribute('aria-label') || element.textContent?.replace(/\s+/g, ' ').trim() || null;
	}

	function generationLabel(job: { kind: string; status: string }) {
		const kind = job.kind === 'image' ? '이미지' : '동영상';
		const status = { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패' }[job.status] ?? job.status;
		return `${kind} · ${status}`;
	}

	function handleClick(event: MouseEvent) {
		const target = event.target;
		if (!(target instanceof Element)) return;
		const element = target.closest('button, a, [role="button"], input[type="checkbox"]');
		if (!(element instanceof HTMLElement)) return;
		if (element instanceof HTMLButtonElement && element.disabled) return;
		const targetType = element.matches('a') ? 'link' : element.matches('input[type="checkbox"]') ? 'checkbox' : 'button';

		void trackWebEvent({
			event_type: 'click',
			page_path: currentPath(),
			target_type: targetType,
			target_id: element.id || null,
			target_label: targetLabel(element),
			target_href: element.getAttribute('href')
		});
	}

	afterNavigate(({ from, to }) => {
		if (!browser || !to) return;
		const pagePath = `${to.url.pathname}${to.url.search}`;
		void trackWebEvent({
			event_type: 'route',
			page_path: pagePath,
			from_path: from ? `${from.url.pathname}${from.url.search}` : null,
			target_type: 'route',
			target_label: pagePath,
			target_href: pagePath
		});
	});

	onMount(() => {
		themeStore.initialize();
		void authStore.initialize().then(() => generationJobStore.initialize());
		document.addEventListener('click', handleClick, true);
		return () => document.removeEventListener('click', handleClick, true);
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}

{#if generationJobStore.list.length > 0}
	<aside class="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:left-auto sm:w-96" aria-live="polite" aria-label="생성 상태">
		{#each generationJobStore.list.slice(0, 3) as job (job.key)}
			<div class="pointer-events-auto w-full rounded-xl border border-border bg-card p-3 text-sm shadow-lg">
				<div class="flex items-center justify-between gap-3">
					<span class="font-semibold">{generationLabel(job)}</span>
					{#if job.status === 'completed' || job.status === 'failed'}
						<button type="button" class="text-xs text-muted-foreground hover:text-foreground" aria-label="생성 상태 닫기" onclick={() => generationJobStore.dismiss(job.key)}>닫기</button>
					{/if}
				</div>
				{#if job.status === 'completed'}
					<p class="mt-1 text-xs text-muted-foreground">생성 결과가 보관함에 저장되었습니다.</p>
				{:else if job.status === 'failed'}
					<p class="mt-1 text-xs text-destructive">{job.error ?? '생성에 실패했습니다.'}</p>
				{:else}
					<p class="mt-1 text-xs text-muted-foreground">화면을 이동해도 서버에서 계속 처리됩니다.</p>
				{/if}
			</div>
		{/each}
	</aside>
{/if}
