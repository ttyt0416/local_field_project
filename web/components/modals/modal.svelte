<script lang="ts">
	import { X } from '@lucide/svelte';
	import type { Snippet } from 'svelte';

	type Props = {
		open?: boolean;
		title: string;
		description?: string;
		children?: Snippet;
		footer?: Snippet;
		closeOnBackdrop?: boolean;
		onclose?: () => void;
	};

	let {
		open = $bindable(false),
		title,
		description,
		children,
		footer,
		closeOnBackdrop = true,
		onclose
	}: Props = $props();

	let closeButton = $state<HTMLButtonElement | undefined>();

	function close() {
		open = false;
		onclose?.();
	}

	function handleKeydown(event: KeyboardEvent) {
		if (open && event.key === 'Escape') {
			close();
		}
	}

	function handleBackdropClick(event: MouseEvent) {
		if (closeOnBackdrop && event.target === event.currentTarget) {
			close();
		}
	}

	$effect(() => {
		if (open) {
			closeButton?.focus();
		}
	});
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<dialog
		open
		class="fixed inset-0 z-50 m-0 flex h-full w-full max-w-none items-end justify-center border-0 bg-black/60 p-4 sm:items-center"
		aria-modal="true"
		aria-labelledby="modal-title"
		aria-describedby={description ? 'modal-description' : undefined}
		onclick={handleBackdropClick}
	>
		<div class="max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-card text-card-foreground shadow-2xl">
			<header class="flex items-start justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
				<div class="min-w-0">
					<h2 id="modal-title" class="text-lg font-semibold tracking-tight">{title}</h2>
					{#if description}
						<p id="modal-description" class="mt-1 text-sm leading-5 text-muted-foreground">{description}</p>
					{/if}
				</div>
				<button
					bind:this={closeButton}
					type="button"
					class="inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					aria-label="모달 닫기"
					onclick={close}
				>
					<X size={18} strokeWidth={1.8} />
				</button>
			</header>

			<div class="px-5 py-5 sm:px-6">
				{#if children}
					{@render children()}
				{/if}
			</div>

			{#if footer}
				<footer class="flex flex-col-reverse gap-2 border-t border-border bg-muted/40 px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
					{@render footer()}
				</footer>
			{/if}
		</div>
	</dialog>
{/if}
