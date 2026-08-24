<script lang="ts">
	import { browser } from '$app/environment';
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte';
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

	function handleClick(event: MouseEvent) {
		const target = event.target;
		if (!(target instanceof Element)) return;
		const element = target.closest('button, a, [role="button"]');
		if (!(element instanceof HTMLElement)) return;
		if (element instanceof HTMLButtonElement && element.disabled) return;

		void trackWebEvent({
			event_type: 'click',
			page_path: currentPath(),
			target_type: element.matches('a') ? 'link' : 'button',
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
		void authStore.initialize();
		document.addEventListener('click', handleClick, true);
		return () => document.removeEventListener('click', handleClick, true);
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
