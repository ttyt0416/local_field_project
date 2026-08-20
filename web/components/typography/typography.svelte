<script lang="ts">
	import type { Snippet } from 'svelte';

	type Variant = 'display' | 'h1' | 'h2' | 'h3' | 'body' | 'muted' | 'label' | 'eyebrow' | 'caption';
	type Element = 'p' | 'span' | 'h1' | 'h2' | 'h3' | 'h4' | 'div';
	type Props = {
		children: Snippet;
		as?: Element;
		variant?: Variant;
		class?: string;
	};

	const variantClasses: Record<Variant, string> = {
		display: 'text-4xl font-semibold tracking-[-0.04em] text-foreground sm:text-5xl lg:text-6xl',
		h1: 'text-3xl font-semibold tracking-tight text-foreground sm:text-4xl',
		h2: 'text-2xl font-semibold tracking-tight text-foreground',
		h3: 'text-lg font-semibold text-foreground',
		body: 'text-sm leading-6 text-foreground',
		muted: 'text-sm leading-6 text-muted-foreground',
		label: 'text-sm font-medium text-foreground',
		eyebrow: 'text-xs font-semibold uppercase tracking-[0.2em] text-primary',
		caption: 'text-xs leading-5 text-muted-foreground'
	};

	let { children, as = 'p', variant = 'body', class: className = '' }: Props = $props();
</script>

<svelte:element this={as} class={`${variantClasses[variant]} ${className}`}>
	{@render children()}
</svelte:element>
