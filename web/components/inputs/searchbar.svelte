<script lang="ts">
	import { Search, X } from '@lucide/svelte';

	type Props = {
		id?: string;
		value?: string;
		placeholder?: string;
		label?: string;
		disabled?: boolean;
		class?: string;
		oninput?: (event: Event) => void;
	};

	let {
		id = 'search',
		value = $bindable(''),
		placeholder = '프롬프트로 검색',
		label = '검색',
		disabled = false,
		class: className = '',
		oninput
	}: Props = $props();

	function clear() {
		value = '';
		oninput?.(new Event('input'));
	}
</script>

<div class={`relative ${className}`}>
	<label for={id} class="sr-only">{label}</label>
	<Search class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={18} strokeWidth={1.8} />
	<input
		{id}
		bind:value
		{placeholder}
		{disabled}
		autocomplete="off"
		aria-label={label}
		oninput={oninput}
		class="h-11 w-full rounded-lg border border-input bg-background pl-10 pr-10 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
	/>
	{#if value}
		<button
			type="button"
			class="absolute right-2 top-1/2 inline-flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			aria-label="검색어 지우기"
			onclick={clear}
		>
			<X size={16} strokeWidth={1.8} />
		</button>
	{/if}
</div>
