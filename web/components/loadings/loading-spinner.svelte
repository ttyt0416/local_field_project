<script lang="ts">
	type Size = 'sm' | 'md' | 'lg';
	type Props = {
		size?: Size;
		label?: string;
		class?: string;
	};

	const sizeClasses: Record<Size, string> = {
		sm: 'size-3.5 border-2',
		md: 'size-5 border-2',
		lg: 'size-8 border-[3px]'
	};

	let { size = 'md', label = '불러오는 중', class: className = '' }: Props = $props();
</script>

<span class={`inline-flex items-center justify-center text-current ${className}`} role="status" aria-label={label}>
	<span class={`animate-spin rounded-full border-current border-t-transparent ${sizeClasses[size]}`} aria-hidden="true"></span>
	<span class="sr-only">{label}</span>
</span>
