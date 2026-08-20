<script lang="ts">
	import type { HTMLInputTypeAttribute } from 'svelte/elements';

	type Props = {
		id?: string;
		name?: string;
		label?: string;
		hint?: string;
		error?: string;
		type?: HTMLInputTypeAttribute;
		placeholder?: string;
		autocomplete?: HTMLInputElement['autocomplete'];
		value?: string;
		disabled?: boolean;
		required?: boolean;
		class?: string;
	};

	let {
		id = 'input',
		name,
		label,
		hint,
		error,
		type = 'text',
		placeholder,
		autocomplete,
		value = $bindable(''),
		disabled = false,
		required = false,
		class: className = ''
	}: Props = $props();
</script>

<div class={`space-y-2 ${className}`}>
	{#if label}
		<label for={id} class="block text-sm font-medium text-foreground">
			{label}
			{#if required}<span class="ml-1 text-destructive" aria-hidden="true">*</span>{/if}
		</label>
	{/if}

	<input
		{id}
		{name}
		{type}
		{placeholder}
		{autocomplete}
		bind:value
		{disabled}
		{required}
		aria-invalid={error ? 'true' : undefined}
		aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
		class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
	/>

	{#if error}
		<p id={`${id}-error`} class="text-xs text-destructive">{error}</p>
	{:else if hint}
		<p id={`${id}-hint`} class="text-xs text-muted-foreground">{hint}</p>
	{/if}
</div>
