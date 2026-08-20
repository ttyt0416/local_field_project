<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import LoadingSpinner from '../../components/loadings/loading-spinner.svelte';
	import { APP_NAME } from '$lib/configs/constants';
	import { authStore } from '$lib/stores/auth.svelte';

	onMount(() => {
		void redirectFromHome();
	});

	async function redirectFromHome() {
		await authStore.initialize();
		await goto(authStore.isAuthenticated ? '/vault' : '/login', { replaceState: true });
	}
</script>

<svelte:head>
	<title>{APP_NAME}</title>
</svelte:head>

<div class="flex min-h-screen items-center justify-center bg-background">
	<LoadingSpinner size="lg" label="페이지를 이동하는 중" />
</div>
