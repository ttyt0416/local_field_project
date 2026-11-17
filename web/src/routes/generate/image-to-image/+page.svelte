<script lang="ts">
	import { imageGenerationStore } from '$lib/stores/image-generation.svelte';
	import ImageToImageGenerator from '../../../../components/generation/image-to-image-generator.svelte';

	type Family = 'anima' | 'minimax_h3_image';
	let family = $state<Family>(imageGenerationStore.pending?.model_family === 'minimax_h3_image' ? 'minimax_h3_image' : 'anima');
</script>

{#key family}
	<ImageToImageGenerator {family} onselect={(nextFamily) => (family = nextFamily)} />
{/key}
