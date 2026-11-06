<script lang="ts">
	import { browser } from '$app/environment';
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';

	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
	import { installInteractionAudit, trackWebEvent } from '$lib/utils/telemetry';
	import { installImageFocusTracking } from '$lib/utils/image-timing';
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();

	afterNavigate(({ from, to, type }) => {
		if (!browser || !to) return;
		const pagePath = `${to.url.pathname}${to.url.search}${to.url.hash}`;
		void trackWebEvent({
			event_type: 'route',
			page_path: pagePath,
			from_path: from ? `${from.url.pathname}${from.url.search}${from.url.hash}` : null,
			target_type: 'route',
			target_label: pagePath,
			target_href: pagePath,
			target_context: { navigation_type: type, from_route: from?.route.id, to_route: to.route.id }
		});
	});

	onMount(() => {
		const disposeFocus = installImageFocusTracking();
		try { localStorage.removeItem('local-field.access-token'); } catch {}
		themeStore.initialize();
		void generationJobStore.initialize();
		const disposeAudit = installInteractionAudit();
		return () => { disposeAudit(); disposeFocus(); };
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
