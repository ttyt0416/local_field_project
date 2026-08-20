<script lang="ts">
	type Props = {
		class?: string;
		label?: string;
		rounded?: boolean;
	};

	let { class: className = '', label = '불러오는 중', rounded = false }: Props = $props();
</script>

<div
	class={`animate-pulse bg-muted ${rounded ? 'rounded-full' : 'rounded-lg'} ${className}`}
	role="status"
	aria-label={label}
	aria-busy="true"
></div>
