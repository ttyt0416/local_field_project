<script lang="ts">
	import { imageGenerationStore } from '$lib/stores/image-generation.svelte';
	import TextToImageGenerator from '../../../../components/generation/text-to-image-generator.svelte';

	type Family = 'anima' | 'illustrious' | 'moss';
	function initialFamily(): Family {
		const value = imageGenerationStore.pending?.model_family;
		return value === 'moss' || value === 'illustrious' ? value : 'anima';
	}
	let modelFamily = $state<Family>(initialFamily());
</script>

{#key modelFamily}
	<TextToImageGenerator {modelFamily} onselect={(nextFamily) => (modelFamily = nextFamily)} />
{/key}
