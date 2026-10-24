<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Layout from '../../../components/layouts/layout.svelte';
	import Tab from '../../../components/tabs/tab.svelte';
	import PromptLibrary from '../../../components/prompts/prompt-library.svelte';
	import LoadingSpinner from '../../../components/loadings/loading-spinner.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import type { PromptKind } from '$lib/utils/saved-prompts';
	let kind = $state<PromptKind>('image');
	let ready = $state(false);
	onMount(() => { let active = true; void initialize(); async function initialize() { await authStore.initialize(); if (!active) return; if (!authStore.isAuthenticated) { await goto('/login'); return; } ready = true; } return () => { active = false; }; });
</script>

<svelte:head><title>프롬프트 관리 | Local Field</title></svelte:head>
<Layout>
	<div class="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
		<header><h1 class="text-2xl font-semibold">프롬프트 관리</h1><p class="mt-2 text-sm text-muted-foreground">이미지·동영상 프롬프트를 저장하고 생성 화면에서 불러옵니다.</p></header>
		{#if ready}<Tab items={[{value:'image' as const,label:'이미지'},{value:'video' as const,label:'동영상'}]} value={kind} ariaLabel="프롬프트 종류" onselect={(value) => { kind = value; }} />{#key kind}<PromptLibrary {kind} manage />{/key}{:else}<LoadingSpinner label="불러오는 중" />{/if}
	</div>
</Layout>
