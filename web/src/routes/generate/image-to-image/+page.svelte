<script lang="ts">
	import { imageGenerationStore } from '$lib/stores/image-generation.svelte';
	import ImageToImageGenerator from '../../../../components/generation/image-to-image-generator.svelte';

	type Family = 'anima' | 'illustrious' | 'qwen_image_2_1';
	function initialFamily(): Family {
		const value = imageGenerationStore.pending?.model_family;
		return value === 'qwen_image_2_1' || value === 'illustrious' ? value : 'anima';
	}
	let family = $state<Family>(initialFamily());
</script>

{#key family}
	<ImageToImageGenerator {family} onselect={(nextFamily) => (family = nextFamily)} />
{/key}
