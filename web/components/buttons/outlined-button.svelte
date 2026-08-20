<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		children: Snippet;
		type?: 'button' | 'submit' | 'reset';
		disabled?: boolean;
		loading?: boolean;
		active?: boolean;
		deactive?: boolean;
		class?: string;
		onclick?: (event: MouseEvent) => void;
	};

	let {
		children,
		type = 'button',
		disabled = false,
		loading = false,
		active = true,
		deactive = false,
		class: className = '',
		onclick
	}: Props = $props();
</script>

<button
	{type}
	class={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 ${
		deactive
			? 'border-border bg-muted text-muted-foreground'
			: active
				? 'border-primary bg-transparent text-primary hover:bg-primary/10'
				: 'border-border bg-transparent text-muted-foreground hover:bg-muted'
	} ${className}`}
	disabled={disabled || loading || deactive}
	aria-busy={loading}
	aria-disabled={deactive ? 'true' : undefined}
	{onclick}
>
	{#if loading}
		<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true"></span>
	{/if}
	{@render children()}
</button>
