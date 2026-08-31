<script lang="ts">
	import type { Snippet } from 'svelte';

	type Handle = 'move' | 'nw' | 'ne' | 'sw' | 'se';
	type Crop = { x: number; y: number; width: number; height: number };

	let {
		children,
		naturalWidth,
		naturalHeight,
		cropX = $bindable(),
		cropY = $bindable(),
		cropWidth = $bindable(),
		cropHeight = $bindable(),
		minSize = 1,
		maxHeightDvh = 38,
		onchange
	}: {
		children: Snippet;
		naturalWidth: number;
		naturalHeight: number;
		cropX: number;
		cropY: number;
		cropWidth: number;
		cropHeight: number;
		minSize?: number;
		maxHeightDvh?: number;
		onchange?: () => void;
	} = $props();

	let container: HTMLDivElement;
	let drag: { pointerId: number; handle: Handle; startX: number; startY: number; crop: Crop } | null = null;

	function begin(event: PointerEvent, handle: Handle) {
		if (!container || naturalWidth <= 0 || naturalHeight <= 0) return;
		event.preventDefault();
		drag = {
			pointerId: event.pointerId,
			handle,
			startX: event.clientX,
			startY: event.clientY,
			crop: { x: cropX, y: cropY, width: cropWidth, height: cropHeight }
		};
	}

	function move(event: PointerEvent) {
		if (!drag || event.pointerId !== drag.pointerId || !container) return;
		const bounds = container.getBoundingClientRect();
		if (!bounds.width || !bounds.height) return;
		const dx = ((event.clientX - drag.startX) / bounds.width) * naturalWidth;
		const dy = ((event.clientY - drag.startY) / bounds.height) * naturalHeight;
		const start = drag.crop;
		let left = start.x;
		let top = start.y;
		let right = start.x + start.width;
		let bottom = start.y + start.height;

		if (drag.handle === 'move') {
			left = clamp(start.x + dx, 0, naturalWidth - start.width);
			top = clamp(start.y + dy, 0, naturalHeight - start.height);
			right = left + start.width;
			bottom = top + start.height;
		} else {
			if (drag.handle.includes('w')) left = clamp(start.x + dx, 0, right - minSize);
			if (drag.handle.includes('e')) right = clamp(start.x + start.width + dx, left + minSize, naturalWidth);
			if (drag.handle.includes('n')) top = clamp(start.y + dy, 0, bottom - minSize);
			if (drag.handle.includes('s')) bottom = clamp(start.y + start.height + dy, top + minSize, naturalHeight);
		}

		cropX = Math.round(left);
		cropY = Math.round(top);
		cropWidth = Math.max(minSize, Math.round(right - left));
		cropHeight = Math.max(minSize, Math.round(bottom - top));
		onchange?.();
	}

	function end(event: PointerEvent) {
		if (drag?.pointerId === event.pointerId) drag = null;
	}

	function clamp(value: number, minimum: number, maximum: number) {
		return Math.min(maximum, Math.max(minimum, value));
	}
</script>

<svelte:window onpointermove={move} onpointerup={end} onpointercancel={end} />

<div
	bind:this={container}
	class="relative mx-auto overflow-hidden rounded-xl border border-border bg-black touch-none"
	style={`width:min(100%, calc(${maxHeightDvh}dvh * ${naturalWidth} / ${naturalHeight}));aspect-ratio:${naturalWidth}/${naturalHeight};`}
>
	<div class="absolute inset-0">{@render children()}</div>
	<div
		class="pointer-events-none absolute border-2 border-primary shadow-[0_0_0_9999px_rgb(0_0_0/0.45)]"
		style={`left:${(cropX / naturalWidth) * 100}%;top:${(cropY / naturalHeight) * 100}%;width:${(cropWidth / naturalWidth) * 100}%;height:${(cropHeight / naturalHeight) * 100}%;`}
	>
		<button type="button" aria-label="crop 영역 이동" title="crop 영역 이동" onpointerdown={(event) => begin(event, 'move')} class="pointer-events-auto absolute left-1/2 top-0 h-5 w-12 -translate-x-1/2 cursor-move rounded-b-md bg-primary/90"></button>
		<button type="button" aria-label="crop 왼쪽 위 크기 조절" onpointerdown={(event) => begin(event, 'nw')} class="pointer-events-auto absolute -left-2 -top-2 size-4 cursor-nw-resize rounded-full border-2 border-background bg-primary"></button>
		<button type="button" aria-label="crop 오른쪽 위 크기 조절" onpointerdown={(event) => begin(event, 'ne')} class="pointer-events-auto absolute -right-2 -top-2 size-4 cursor-ne-resize rounded-full border-2 border-background bg-primary"></button>
		<button type="button" aria-label="crop 왼쪽 아래 크기 조절" onpointerdown={(event) => begin(event, 'sw')} class="pointer-events-auto absolute -bottom-2 -left-2 size-4 cursor-sw-resize rounded-full border-2 border-background bg-primary"></button>
		<button type="button" aria-label="crop 오른쪽 아래 크기 조절" onpointerdown={(event) => begin(event, 'se')} class="pointer-events-auto absolute -bottom-2 -right-2 size-4 cursor-se-resize rounded-full border-2 border-background bg-primary"></button>
	</div>
</div>
