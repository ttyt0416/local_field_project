<script lang="ts">
	import ImageToImageGenerator from '../../../../components/generation/image-to-image-generator.svelte';

	type Family = 'anima';
	let family = $state<Family>('anima');
</script>

{#key family}
	<ImageToImageGenerator {family} onselect={(nextFamily) => (family = nextFamily)} />
{/key}
