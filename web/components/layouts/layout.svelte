<script lang="ts">
	import type { Snippet } from 'svelte';
	import Body from './body.svelte';
	import Navbar from './navbar.svelte';
	import Sidebar from './sidebar.svelte';

	type Props = {
		children: Snippet;
	};

	let { children }: Props = $props();
	let sidebarOpen = $state(false);
</script>

<Sidebar bind:open={sidebarOpen} />

<div class="min-h-screen bg-muted/30 text-foreground dark:bg-background lg:pl-72">
	<Navbar onMenuClick={() => (sidebarOpen = true)} />
	<Body>
		{@render children()}
	</Body>
</div>
