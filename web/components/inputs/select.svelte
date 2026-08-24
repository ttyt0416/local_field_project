<script lang="ts" generics="T extends string">
	type Option = {
		value: T;
		label: string;
		disabled?: boolean;
	};

	type Props = {
		id?: string;
		name?: string;
		label?: string;
		hint?: string;
		error?: string;
		options: readonly Option[];
		placeholder?: string;
		autocomplete?: boolean;
		value?: T;
		disabled?: boolean;
		required?: boolean;
		class?: string;
	};

	let {
		id = 'select',
		name,
		label,
		hint,
		error,
		options,
		placeholder,
		autocomplete = false,
		value = $bindable(options[0]?.value),
		disabled = false,
		required = false,
		class: className = ''
	}: Props = $props();

	let query = $state('');
	let open = $state(false);
	let activeIndex = $state(-1);
	let autocompleteContainer = $state<HTMLDivElement>();
	let selectedOption = $derived(options.find((option) => option.value === value));
	let filteredOptions = $derived(
		options.filter((option) => option.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
	);
	let listId = $derived(`${id}-options`);

	$effect(() => {
		if (!open) {
			query = selectedOption?.label ?? '';
		}
	});

	function selectOption(option: Option) {
		if (option.disabled) return;
		value = option.value;
		query = option.label;
		open = false;
		activeIndex = -1;
	}

	function moveActive(direction: 1 | -1) {
		if (!open) open = true;
		const enabled = filteredOptions.filter((option) => !option.disabled);
		if (enabled.length === 0) return;
		const currentValue = filteredOptions[activeIndex]?.value;
		const currentPosition = enabled.findIndex((option) => option.value === currentValue);
		const nextPosition = currentPosition < 0 ? (direction === 1 ? 0 : enabled.length - 1) : (currentPosition + direction + enabled.length) % enabled.length;
		activeIndex = filteredOptions.findIndex((option) => option.value === enabled[nextPosition].value);
	}

	function handleInput() {
		open = true;
		activeIndex = -1;
	}

	function handleFocus() {
		open = true;
		query = '';
		activeIndex = -1;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			moveActive(1);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			moveActive(-1);
		} else if (event.key === 'Enter' && open && activeIndex >= 0) {
			event.preventDefault();
			const option = filteredOptions[activeIndex];
			if (option) selectOption(option);
		} else if (event.key === 'Escape') {
			open = false;
			activeIndex = -1;
		}
	}

	function handleWindowClick(event: MouseEvent) {
		if (!open || !autocompleteContainer || !(event.target instanceof Node)) return;
		if (!autocompleteContainer.contains(event.target)) {
			open = false;
			activeIndex = -1;
		}
	}
</script>

<svelte:window onclick={handleWindowClick} />

<div class={`space-y-2 ${className}`}>
	{#if label}
		<label for={id} class="block text-sm font-medium text-foreground">
			{label}
			{#if required}<span class="ml-1 text-destructive" aria-hidden="true">*</span>{/if}
		</label>
	{/if}

	{#if autocomplete}
		<div bind:this={autocompleteContainer} class="relative">
			<input
				{id}
				{name}
				value={query}
				placeholder={placeholder ?? '선택하세요'}
				autocomplete="off"
				role="combobox"
				aria-autocomplete="list"
				aria-expanded={open}
				aria-controls={listId}
				aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
				aria-invalid={error ? 'true' : undefined}
				aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
				disabled={disabled}
				required={required}
				oninput={handleInput}
				onfocus={handleFocus}
				onkeydown={handleKeydown}
				class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
			/>
			{#if name}
				<input type="hidden" {name} value={value ?? ''} />
			{/if}

			{#if open && filteredOptions.length > 0}
				<div class="absolute z-20 mt-2 max-h-60 w-full overflow-y-auto rounded-lg border border-border bg-card p-1 shadow-lg">
					<ul id={listId} role="listbox" aria-label={label ?? '선택 항목'}>
						{#each filteredOptions as option, index (option.value)}
							<li>
								<button
									type="button"
									id={`${listId}-${index}`}
									role="option"
									aria-selected={value === option.value}
									disabled={option.disabled}
									class={`w-full rounded-md px-3 py-2 text-left text-sm transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 ${activeIndex === index || value === option.value ? 'bg-muted text-foreground' : 'text-muted-foreground'}`}
									onclick={() => selectOption(option)}
								>
									{option.label}
								</button>
							</li>
						{/each}
					</ul>
				</div>
			{:else if open}
				<div class="absolute z-20 mt-2 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-muted-foreground shadow-lg" role="status">
					검색 결과가 없습니다.
				</div>
			{/if}
		</div>
	{:else}
		<select
			{id}
			{name}
			bind:value
			{disabled}
			{required}
			aria-invalid={error ? 'true' : undefined}
			aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
			class="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
		>
			{#if placeholder}
				<option value="" disabled hidden>{placeholder}</option>
			{/if}
			{#each options as option (option.value)}
				<option value={option.value} disabled={option.disabled}>{option.label}</option>
			{/each}
		</select>
	{/if}

	{#if error}
		<p id={`${id}-error`} class="text-xs text-destructive">{error}</p>
	{:else if hint}
		<p id={`${id}-hint`} class="text-xs text-muted-foreground">{hint}</p>
	{/if}
</div>
