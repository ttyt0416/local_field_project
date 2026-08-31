<script lang="ts">
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';

	let {
		open = $bindable(false),
		samplers,
		schedulers,
		samplerName = $bindable(),
		scheduler = $bindable()
	}: {
		open: boolean;
		samplers: string[];
		schedulers: string[];
		samplerName: string;
		scheduler: string;
	} = $props();

	let draftSampler = $state('');
	let draftScheduler = $state('');

	$effect(() => {
		if (!open) return;
		draftSampler = samplerName;
		draftScheduler = scheduler;
	});

	function apply() {
		if (!draftSampler || !draftScheduler) return;
		samplerName = draftSampler;
		scheduler = draftScheduler;
		open = false;
	}
</script>

<Modal bind:open title="샘플러 / 스케줄러 선택" description="이미지 생성에 사용할 방식을 각각 선택하세요.">
	<div class="grid gap-5 md:grid-cols-2">
		<section class="space-y-3" aria-labelledby="sampler-list-title">
			<h3 id="sampler-list-title" class="text-sm font-semibold">샘플러</h3>
			<div class="grid max-h-80 grid-cols-2 gap-2 overflow-y-auto pr-1">
				{#each samplers as value}
					<button
						type="button"
						onclick={() => (draftSampler = value)}
						class={`min-h-11 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${draftSampler === value ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}
						aria-pressed={draftSampler === value}
					>
						{value}
					</button>
				{/each}
			</div>
		</section>
		<section class="space-y-3" aria-labelledby="scheduler-list-title">
			<h3 id="scheduler-list-title" class="text-sm font-semibold">스케줄러</h3>
			<div class="grid max-h-80 grid-cols-2 gap-2 overflow-y-auto pr-1">
				{#each schedulers as value}
					<button
						type="button"
						onclick={() => (draftScheduler = value)}
						class={`min-h-11 break-all rounded-lg border px-3 py-2 text-left text-xs transition ${draftScheduler === value ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}
						aria-pressed={draftScheduler === value}
					>
						{value}
					</button>
				{/each}
			</div>
		</section>
	</div>
	<div class="mt-6 flex justify-end gap-2">
		<OutlinedButton onclick={() => (open = false)}>취소</OutlinedButton>
		<PrimaryButton disabled={!draftSampler || !draftScheduler} onclick={apply}>적용</PrimaryButton>
	</div>
</Modal>
