<script lang="ts">
	import { page } from '$app/state';
	import ImageToImageGenerator from '../../../../components/generation/image-to-image-generator.svelte';

	type Family = 'anima' | 'illustrious' | 'qwen_image_2_1';
	function requestedFamily(): Family {
		const value = page.url.searchParams.get('family');
		return value === 'qwen_image_2_1' || value === 'illustrious' ? value : 'anima';
	}
	let family = $state<Family>(requestedFamily());

	$effect(() => {
		family = requestedFamily();
	});
</script>

{#key family}
	<ImageToImageGenerator {family} onselect={(nextFamily) => (family = nextFamily)} />
{/key}
