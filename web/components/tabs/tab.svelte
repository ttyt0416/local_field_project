<script lang="ts" generics="T extends string">
	type TabItem = {
		value: T;
		label: string;
		disabled?: boolean;
	};

	type Props = {
		items: readonly TabItem[];
		value?: T;
		ariaLabel?: string;
		class?: string;
		onselect?: (value: T) => void | boolean;
};

	let {
		items,
		value = $bindable(items[0]?.value),
		ariaLabel = '탭',
		class: className = '',
		onselect
	}: Props = $props();
</script>

<div class={`flex rounded-xl bg-muted p-1 ${className}`} role="tablist" aria-label={ariaLabel}>
	{#each items as item (item.value)}
		<button
			type="button"
			class={`min-w-0 flex-1 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 ${value === item.value ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
			role="tab"
			aria-selected={value === item.value}
			disabled={item.disabled}
			onclick={() => {
				const accepted = onselect?.(item.value);
				if (accepted !== false) value = item.value;
			}}
		>
			{item.label}
		</button>
	{/each}
</div>
