<script lang="ts">
	import { CheckCircle2, Info, X, XCircle } from '@lucide/svelte';

	type ToastState = 'positive' | 'negative' | 'info';
	type Props = {
		state?: ToastState;
		title: string;
		message: string;
		onclose?: () => void;
	};

	let { state = 'info', title, message, onclose }: Props = $props();
	const styles = $derived(
		state === 'positive'
			? 'border-success/30 bg-success/10 text-success'
			: state === 'negative'
				? 'border-destructive/30 bg-destructive/10 text-destructive'
				: 'border-primary/30 bg-primary/10 text-primary'
	);
</script>

<div class={`flex w-[min(24rem,calc(100vw-2rem))] items-start gap-3 rounded-xl border p-4 shadow-lg ${styles}`} role={state === 'negative' ? 'alert' : 'status'} aria-live={state === 'negative' ? 'assertive' : 'polite'}>
	{#if state === 'positive'}
		<CheckCircle2 size={19} strokeWidth={1.9} aria-hidden="true" />
	{:else if state === 'negative'}
		<XCircle size={19} strokeWidth={1.9} aria-hidden="true" />
	{:else}
		<Info size={19} strokeWidth={1.9} aria-hidden="true" />
	{/if}
	<div class="min-w-0 flex-1">
		<p class="text-sm font-semibold">{title}</p>
		<p class="mt-1 text-xs leading-5 text-foreground/75">{message}</p>
	</div>
	{#if onclose}
		<button
			type="button"
			class="inline-flex size-7 shrink-0 items-center justify-center rounded-md transition hover:bg-background/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			aria-label="알림 닫기"
			onclick={onclose}
		>
			<X size={16} strokeWidth={1.8} />
		</button>
	{/if}
</div>
