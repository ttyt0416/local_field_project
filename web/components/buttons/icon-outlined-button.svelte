<script lang="ts">
	import type { Snippet } from 'svelte';
	import LoadingSpinner from '../loadings/loading-spinner.svelte';

	type Props = {
		children: Snippet;
		ariaLabel: string;
		type?: 'button' | 'submit' | 'reset';
		disabled?: boolean;
		loading?: boolean;
		variant?: 'default' | 'destructive';
		class?: string;
		pressed?: boolean;
		onclick?: (event: MouseEvent) => void;
	};

	let {
		children,
		ariaLabel,
		type = 'button',
		disabled = false,
		loading = false,
		variant = 'default',
		class: className = '',
		pressed,
		onclick
	}: Props = $props();
</script>

<button
	{type}
	class={`inline-flex size-10 shrink-0 items-center justify-center rounded-lg transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 ${
		variant === 'destructive'
			? 'border border-destructive bg-destructive text-destructive-foreground hover:border-destructive hover:bg-destructive/90 hover:text-destructive-foreground'
			: 'border border-border bg-transparent text-muted-foreground hover:border-primary/50 hover:bg-primary/10 hover:text-primary'
	} ${className}`}
	disabled={disabled || loading}
	aria-label={ariaLabel}
	aria-pressed={pressed}
	aria-busy={loading}
	{onclick}
>
	{#if loading}
		<LoadingSpinner size="sm" label={ariaLabel} />
	{:else}
		{@render children()}
	{/if}
</button>
