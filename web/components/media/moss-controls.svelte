<script lang="ts">
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import { mossSettings, type MossSettings, type MossLayoutElement } from '$lib/types/moss';

	let { value = $bindable(mossSettings()), width, height, disabled = false, dmdAvailable = false, ondmd }: {
		value?: MossSettings; width: number; height: number; disabled?: boolean;
		dmdAvailable?: boolean; ondmd?: () => void;
	} = $props();
	let canvas = $state<HTMLDivElement>();
	let selected = $state(0);
	let drag: { pointerId: number; index: number; handle: 'move' | 'resize'; startX: number; startY: number; box: MossLayoutElement } | null = null;
	const inputClass = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm disabled:opacity-50';

	function add(kind: MossLayoutElement['kind']) {
		if (disabled || value.elements.length >= 32) return;
		const offset = 0.08 + (value.elements.length % 6) * 0.04;
		value.elements = [...value.elements, { kind, caption: kind === 'character' ? '인물' : kind === 'object' ? '사물' : '', text: kind === 'text' ? '텍스트' : '', x: offset, y: offset, width: 0.4, height: 0.25 }];
		selected = value.elements.length - 1;
	}

	function begin(event: PointerEvent, index: number, handle: 'move' | 'resize') {
		if (disabled) return;
		event.preventDefault();
		selected = index;
		drag = { pointerId: event.pointerId, index, handle, startX: event.clientX, startY: event.clientY, box: { ...value.elements[index] } };
	}

	function move(event: PointerEvent) {
		if (!drag || event.pointerId !== drag.pointerId || !canvas || disabled) return;
		const bounds = canvas.getBoundingClientRect();
		if (!bounds.width || !bounds.height) return;
		const dx = (event.clientX - drag.startX) / bounds.width;
		const dy = (event.clientY - drag.startY) / bounds.height;
		const box = { ...drag.box };
		if (drag.handle === 'move') {
			box.x = Math.max(0, Math.min(1 - box.width, box.x + dx));
			box.y = Math.max(0, Math.min(1 - box.height, box.y + dy));
		} else {
			box.width = Math.max(0.02, Math.min(1 - box.x, box.width + dx));
			box.height = Math.max(0.02, Math.min(1 - box.y, box.height + dy));
		}
		value.elements = value.elements.map((element, index) => index === drag!.index ? box : element);
	}

	function end(event: PointerEvent) {
		if (drag?.pointerId === event.pointerId) drag = null;
	}

	function coordinate(index: number, key: 'x' | 'y' | 'width' | 'height', raw: string) {
		const box = { ...value.elements[index] };
		const number = Number(raw) / 100;
		if (!Number.isFinite(number)) return;
		if (key === 'x') box.x = Math.max(0, Math.min(1 - box.width, number));
		if (key === 'y') box.y = Math.max(0, Math.min(1 - box.height, number));
		if (key === 'width') box.width = Math.max(0.02, Math.min(1 - box.x, number));
		if (key === 'height') box.height = Math.max(0.02, Math.min(1 - box.y, number));
		value.elements = value.elements.map((element, i) => i === index ? box : element);
	}
</script>

<svelte:window onpointermove={move} onpointerup={end} onpointercancel={end} />

<fieldset disabled={disabled} class="min-w-0 space-y-4 rounded-xl border border-border p-4">
	<legend class="px-2 text-sm font-semibold">MOSS 설정</legend>
	<div class="flex flex-wrap items-center gap-3">
		<OutlinedButton type="button" disabled={disabled || !dmdAvailable} onclick={ondmd}>8스텝 DMD 적용</OutlinedButton>
		<span class="text-xs text-muted-foreground">DMD LoRA 0.7 · 8 steps · CFG 1</span>
	</div>
	<label class="flex items-center gap-2 text-sm font-medium"><input type="checkbox" bind:checked={value.layout_enabled} />레이아웃 지정</label>
	{#if value.layout_enabled}
		<p class="text-xs leading-5 text-muted-foreground">박스를 이동하고 오른쪽 아래 모서리로 크기를 조절하세요. 위치는 생성 가이드이며 결과가 정확히 일치하지 않을 수 있습니다.</p>
		<div class="flex flex-wrap gap-2"><OutlinedButton type="button" disabled={disabled || value.elements.length >= 32} onclick={() => add('object')}>사물 추가</OutlinedButton><OutlinedButton type="button" disabled={disabled || value.elements.length >= 32} onclick={() => add('character')}>인물 추가</OutlinedButton><OutlinedButton type="button" disabled={disabled || value.elements.length >= 32} onclick={() => add('text')}>텍스트 추가</OutlinedButton></div>
		<div bind:this={canvas} class="relative mx-auto touch-none overflow-hidden rounded-lg border border-border bg-muted/40" style={`width:min(100%, calc(48dvh * ${width || 1024} / ${height || 1024}));aspect-ratio:${width || 1024}/${height || 1024};background-image:linear-gradient(to right,#8882 1px,transparent 1px),linear-gradient(to bottom,#8882 1px,transparent 1px);background-size:10% 10%;`}>
			{#each value.elements as element, index}
				<div class={`absolute border-2 ${index === selected ? 'border-primary bg-primary/15' : 'border-muted-foreground bg-background/40'}`} style={`left:${element.x * 100}%;top:${element.y * 100}%;width:${element.width * 100}%;height:${element.height * 100}%;`}>
					<button type="button" disabled={disabled} aria-label={`영역 ${index + 1} 선택 및 이동`} onclick={() => selected = index} onpointerdown={(event) => begin(event, index, 'move')} class="absolute inset-0 overflow-hidden p-1 text-left text-xs">{index + 1}. {element.kind === 'text' ? element.text : element.caption}</button>
					{#if index === selected}<button type="button" disabled={disabled} aria-label={`영역 ${index + 1} 크기 조절`} onpointerdown={(event) => begin(event, index, 'resize')} class="absolute -bottom-1 -right-1 size-4 cursor-se-resize rounded-sm border border-background bg-primary"></button>{/if}
				</div>
			{/each}
		</div>
		{#each value.elements as element, index}
			<div class={`space-y-3 rounded-lg border p-3 ${index === selected ? 'border-primary' : 'border-border'}`}>
				<div class="flex items-center justify-between gap-2"><button type="button" onclick={() => selected = index} class="text-sm font-semibold">영역 {index + 1} · {element.kind === 'text' ? '텍스트' : element.kind === 'character' ? '인물' : '사물'}</button><OutlinedButton type="button" disabled={disabled} onclick={() => { value.elements = value.elements.filter((_, i) => i !== index); selected = Math.max(0, selected - 1); }}>삭제</OutlinedButton></div>
				<label class="block space-y-1"><span class="text-xs">영역 설명</span><textarea rows="2" maxlength="500" bind:value={element.caption} class={inputClass}></textarea></label>
				{#if element.kind === 'text'}<label class="block space-y-1"><span class="text-xs">표시할 텍스트</span><textarea rows="2" maxlength="200" required bind:value={element.text} class={inputClass}></textarea></label>{/if}
				<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">{#each ['x', 'y', 'width', 'height'] as key}<label class="space-y-1"><span class="text-xs">{key === 'x' ? '왼쪽' : key === 'y' ? '위쪽' : key === 'width' ? '너비' : '높이'} (%)</span><input type="number" min="0" max="100" step="0.1" value={Math.round(element[key as 'x' | 'y' | 'width' | 'height'] * 1000) / 10} oninput={(event) => coordinate(index, key as 'x' | 'y' | 'width' | 'height', event.currentTarget.value)} class={inputClass} /></label>{/each}</div>
			</div>
		{/each}
	{/if}
</fieldset>
