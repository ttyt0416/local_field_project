<script lang="ts">
	import Layout from '../../../../components/layouts/layout.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import MeshPanel from './mesh-panel.svelte';
	import RiggingPanel from './rigging-panel.svelte';

	const tabs = [{ value: 'mesh' as const, label: 'MESH' }, { value: 'rigging' as const, label: 'RIGGING' }];
	let selected = $state<'mesh' | 'rigging'>('mesh');
</script>

<svelte:head>
	<title>3D · Local Field</title>
	<meta name="description" content="3D 메시 생성과 자동 리깅" />
</svelte:head>

<Layout>
	<div class="space-y-6">
		<Typography as="h1" variant="display">3D</Typography>
		<Tab items={tabs} bind:value={selected} ariaLabel="3D 작업" class="max-w-md" />
		{#if selected === 'mesh'}
			<MeshPanel />
		{:else}
			<RiggingPanel />
		{/if}
	</div>
</Layout>
