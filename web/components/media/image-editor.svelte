<script lang="ts">
	import { browser } from '$app/environment';
	import { RotateCw } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import LoadingSpinner from '../loadings/loading-spinner.svelte';
	import { apiBlob, apiForm } from '$lib/utils/api';

	type Props = {
		open?: boolean;
		generationId: string;
		sourcePath?: string;
		editPath?: string;
		onsaved?: (generationId: string) => void;
		onerror?: (message: string) => void;
	};

	let {
		open = $bindable(false),
		generationId,
		sourcePath,
		editPath,
		onsaved,
		onerror
	}: Props = $props();

	let canvas = $state<HTMLCanvasElement>();
	let image = $state<HTMLImageElement>();
	let loading = $state(false);
	let saving = $state(false);
	let imageWidth = $state(0);
	let imageHeight = $state(0);
	let cropX = $state(0);
	let cropY = $state(0);
	let cropWidth = $state(0);
	let cropHeight = $state(0);
	let rotation = $state<0 | 90 | 180 | 270>(0);
	let zoom = $state(1);
	let objectUrl = '';

	$effect(() => {
		if (!open || !browser || !generationId) return;
		let cancelled = false;
		loading = true;
		image = undefined;
		void apiBlob(sourcePath ?? `vault/images/${generationId}/source`)
			.then((blob) => {
				if (cancelled) return;
				if (objectUrl) URL.revokeObjectURL(objectUrl);
				objectUrl = URL.createObjectURL(blob);
				const nextImage = new Image();
				nextImage.onload = () => {
					if (cancelled) return;
					image = nextImage;
					imageWidth = nextImage.naturalWidth;
					imageHeight = nextImage.naturalHeight;
					cropX = 0;
					cropY = 0;
					cropWidth = imageWidth;
					cropHeight = imageHeight;
					rotation = 0;
					zoom = 1;
					loading = false;
					drawPreview();
				};
				nextImage.onerror = () => {
					if (!cancelled) {
						loading = false;
						onerror?.('이미지 원본을 불러오지 못했습니다.');
					}
				};
				nextImage.src = objectUrl;
			})
			.catch((reason) => {
				if (!cancelled) {
					loading = false;
					onerror?.(reason instanceof Error ? reason.message : '이미지 원본을 불러오지 못했습니다.');
				}
			});
		return () => {
			cancelled = true;
			if (objectUrl) {
				URL.revokeObjectURL(objectUrl);
				objectUrl = '';
			}
		};
	});

	function clampCrop() {
		cropX = Math.max(0, Math.min(Math.round(cropX), imageWidth - 1));
		cropY = Math.max(0, Math.min(Math.round(cropY), imageHeight - 1));
		cropWidth = Math.max(1, Math.min(Math.round(cropWidth), imageWidth - cropX));
		cropHeight = Math.max(1, Math.min(Math.round(cropHeight), imageHeight - cropY));
	}

	function drawPreview() {
		if (!canvas || !image || !cropWidth || !cropHeight) return;
		clampCrop();
		const clockwise = rotation === 90 || rotation === 270;
		canvas.width = clockwise ? cropHeight : cropWidth;
		canvas.height = clockwise ? cropWidth : cropHeight;
		const context = canvas.getContext('2d');
		if (!context) return;
		context.clearRect(0, 0, canvas.width, canvas.height);
		context.save();
		if (rotation === 90) {
			context.translate(cropHeight, 0);
			context.rotate(Math.PI / 2);
		} else if (rotation === 180) {
			context.translate(cropWidth, cropHeight);
			context.rotate(Math.PI);
		} else if (rotation === 270) {
			context.translate(0, cropWidth);
			context.rotate(-Math.PI / 2);
		}
		const sourceWidth = cropWidth / zoom;
		const sourceHeight = cropHeight / zoom;
		const sourceX = cropX + (cropWidth - sourceWidth) / 2;
		const sourceY = cropY + (cropHeight - sourceHeight) / 2;
		context.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, cropWidth, cropHeight);
		context.restore();
	}

	function resetCrop() {
		cropX = 0;
		cropY = 0;
		cropWidth = imageWidth;
		cropHeight = imageHeight;
		zoom = 1;
		drawPreview();
	}

	function rotateRight() {
		rotation = ((rotation + 90) % 360) as 0 | 90 | 180 | 270;
		drawPreview();
	}

	function save() {
		const outputCanvas = canvas;
		if (!outputCanvas || !image || saving) return;
		saving = true;
		outputCanvas.toBlob(async (blob) => {
			if (!blob) {
				saving = false;
				onerror?.('편집한 이미지를 만들지 못했습니다.');
				return;
			}
			const form = new FormData();
			form.append('file', blob, 'local-field-edited.png');
			form.append('width', String(outputCanvas.width));
			form.append('height', String(outputCanvas.height));
			try {
				const result = await apiForm<{ generation_id: string }>(editPath ?? `vault/images/${generationId}/edit`, form);
				open = false;
				onsaved?.(result.generation_id);
			} catch (reason) {
				onerror?.(reason instanceof Error ? reason.message : '편집한 이미지를 저장하지 못했습니다.');
			} finally {
				saving = false;
			}
		}, 'image/png');
	}
</script>

<Modal bind:open title="이미지 편집" description="crop과 회전 결과를 새 콘텐츠로 저장합니다." closeOnBackdrop={!saving}>
	{#if loading}
		<div class="flex min-h-64 items-center justify-center"><LoadingSpinner size="lg" label="이미지 원본을 불러오는 중" /></div>
	{:else if image}
		<div class="space-y-5">
			<div class="flex min-h-56 items-center justify-center overflow-auto rounded-xl bg-black p-3">
				<canvas bind:this={canvas} class="max-h-[38dvh] max-w-full object-contain" aria-label="이미지 편집 미리보기"></canvas>
			</div>
			<div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
				<label class="space-y-1"><span class="text-muted-foreground">X</span><input type="number" min="0" max={Math.max(0, imageWidth - 1)} bind:value={cropX} oninput={drawPreview} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
				<label class="space-y-1"><span class="text-muted-foreground">Y</span><input type="number" min="0" max={Math.max(0, imageHeight - 1)} bind:value={cropY} oninput={drawPreview} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
				<label class="space-y-1"><span class="text-muted-foreground">가로</span><input type="number" min="1" max={imageWidth} bind:value={cropWidth} oninput={drawPreview} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
				<label class="space-y-1"><span class="text-muted-foreground">세로</span><input type="number" min="1" max={imageHeight} bind:value={cropHeight} oninput={drawPreview} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
			</div>
			<label class="block space-y-2 text-sm"><span class="flex justify-between text-muted-foreground"><span>확대</span><strong class="text-foreground">{zoom.toFixed(1)}x</strong></span><input type="range" min="1" max="3" step="0.1" bind:value={zoom} oninput={drawPreview} class="w-full accent-primary" /></label>
			<div class="flex flex-wrap items-center justify-between gap-2">
				<span class="text-xs text-muted-foreground">원본 {imageWidth} × {imageHeight} · 회전 {rotation}°</span>
				<div class="flex gap-2">
					<OutlinedButton onclick={resetCrop}>전체 이미지</OutlinedButton>
					<OutlinedButton onclick={rotateRight}><RotateCw size={16} strokeWidth={1.9} />회전</OutlinedButton>
				</div>
			</div>
		</div>
	{:else}
		<div class="flex min-h-64 items-center justify-center text-sm text-muted-foreground">이미지 편집을 준비할 수 없습니다.</div>
	{/if}
	{#snippet footer()}
		<OutlinedButton disabled={saving} onclick={() => (open = false)}>취소</OutlinedButton>
		<PrimaryButton loading={saving} disabled={!image || loading} onclick={() => void save()}>편집 결과 저장</PrimaryButton>
	{/snippet}
</Modal>
