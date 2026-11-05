<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import LoadingSpinner from '../../components/loadings/loading-spinner.svelte';
	import { APP_NAME } from '$lib/configs/constants';


	onMount(() => {
		void redirectFromHome();
	});

	async function redirectFromHome() {
		await goto('/vault', { replaceState: true });
	}
</script>

<svelte:head>
	<title>{APP_NAME}</title>
</svelte:head>

<div class="flex min-h-screen items-center justify-center bg-background">
	<LoadingSpinner size="lg" label="페이지를 이동하는 중" />
</div>
