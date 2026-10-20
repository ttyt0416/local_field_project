<script lang="ts">
	import { page } from '$app/state';
	import TextToImageGenerator from '../../../../components/generation/text-to-image-generator.svelte';

	type Family = 'anima' | 'illustrious' | 'moss';
	function requestedFamily(): Family {
		const value = page.url.searchParams.get('family');
		return value === 'moss' || value === 'illustrious' ? value : 'anima';
	}
	let modelFamily = $state<Family>(requestedFamily());

	$effect(() => {
		modelFamily = requestedFamily();
	});
</script>

{#key modelFamily}
	<TextToImageGenerator {modelFamily} onselect={(nextFamily) => (modelFamily = nextFamily)} />
{/key}
