<script lang="ts">
	import { RotateCw } from '@lucide/svelte';
	import Modal from '../modals/modal.svelte';
	import OutlinedButton from '../buttons/outlined-button.svelte';
	import PrimaryButton from '../buttons/primary-button.svelte';
	import CropSelector from './crop-selector.svelte';
	import { apiJson } from '$lib/utils/api';

	type Props = {
		open?: boolean;
		generationId: string;
		videoUrl: string;
		editPath?: string;
		onsaved?: (generationId: string) => void;
		onerror?: (message: string) => void;
	};

	let {
		open = $bindable(false),
		generationId,
		videoUrl,
		editPath,
		onsaved,
		onerror
	}: Props = $props();

	let video = $state<HTMLVideoElement>();
	let saving = $state(false);
	let duration = $state(0);
	let videoWidth = $state(0);
	let videoHeight = $state(0);
	let startSeconds = $state(0);
	let endSeconds = $state(0);
	let cropX = $state(0);
	let cropY = $state(0);
	let cropWidth = $state(0);
	let cropHeight = $state(0);
	let rotation = $state<0 | 90 | 180 | 270>(0);

	function loadMetadata() {
		if (!video) return;
		duration = video.duration;
		videoWidth = video.videoWidth;
		videoHeight = video.videoHeight;
		startSeconds = 0;
		endSeconds = duration;
		cropX = 0;
		cropY = 0;
		cropWidth = videoWidth;
		cropHeight = videoHeight;
		rotation = 0;
	}

	function clampValues() {
		if (!duration || !videoWidth || !videoHeight) return;
		startSeconds = Math.max(0, Math.min(startSeconds, Math.max(0, duration - 0.1)));
		endSeconds = Math.max(startSeconds + 0.1, Math.min(endSeconds, duration));
		cropX = Math.max(0, Math.min(Math.round(cropX), videoWidth - 2));
		cropY = Math.max(0, Math.min(Math.round(cropY), videoHeight - 2));
		cropWidth = Math.max(2, Math.min(Math.round(cropWidth), videoWidth - cropX));
		cropHeight = Math.max(2, Math.min(Math.round(cropHeight), videoHeight - cropY));
	}

	function resetCrop() {
		cropX = 0;
		cropY = 0;
		cropWidth = videoWidth;
		cropHeight = videoHeight;
	}

	function rotateRight() {
		rotation = ((rotation + 90) % 360) as 0 | 90 | 180 | 270;
	}

	async function save() {
		if (!video || !duration || saving) return;
		clampValues();
		saving = true;
		try {
			const result = await apiJson<{ generation_id: string }>(editPath ?? `vault/videos/${generationId}/edit`, {
				method: 'POST',
				json: {
					start_seconds: startSeconds,
					end_seconds: endSeconds,
					crop_x: cropX,
					crop_y: cropY,
					crop_width: cropWidth,
					crop_height: cropHeight,
					rotate: rotation
				},
				timeout: 240_000
			});
			open = false;
			onsaved?.(result.generation_id);
		} catch (reason) {
			onerror?.(reason instanceof Error ? reason.message : '편집한 영상을 저장하지 못했습니다.');
		} finally {
			saving = false;
		}
	}
</script>

<Modal bind:open title="동영상 편집" description="구간, crop과 회전 결과를 새 콘텐츠로 저장합니다." closeOnBackdrop={!saving}>
	<div class="space-y-5">
		<CropSelector
			naturalWidth={videoWidth || 16}
			naturalHeight={videoHeight || 9}
			bind:cropX
			bind:cropY
			bind:cropWidth
			bind:cropHeight
			minSize={2}
			maxHeightDvh={34}
			onchange={clampValues}
		>
			<video
				bind:this={video}
				src={videoUrl}
				controls
				playsinline
				preload="metadata"
				onloadedmetadata={loadMetadata}
				onerror={() => onerror?.('영상 원본을 불러오지 못했습니다.')}
				class="h-full w-full bg-black object-fill"
			>
				<track kind="captions" srclang="ko" label="자막 없음" src="data:text/vtt,WEBVTT" />
				영상을 재생할 수 없습니다.
			</video>
		</CropSelector>
		{#if duration > 0}
			<div class="grid grid-cols-2 gap-3 text-sm">
				<label class="space-y-1"><span class="text-muted-foreground">시작 시간(초)</span><input type="number" min="0" max={duration} step="0.1" bind:value={startSeconds} oninput={clampValues} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
				<label class="space-y-1"><span class="text-muted-foreground">종료 시간(초)</span><input type="number" min="0.1" max={duration} step="0.1" bind:value={endSeconds} oninput={clampValues} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
			</div>
			<div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
				<label class="space-y-1"><span class="text-muted-foreground">X</span><input type="number" min="0" max={Math.max(0, videoWidth - 2)} bind:value={cropX} oninput={clampValues} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
				<label class="space-y-1"><span class="text-muted-foreground">Y</span><input type="number" min="0" max={Math.max(0, videoHeight - 2)} bind:value={cropY} oninput={clampValues} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
				<label class="space-y-1"><span class="text-muted-foreground">가로</span><input type="number" min="2" max={videoWidth} bind:value={cropWidth} oninput={clampValues} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
				<label class="space-y-1"><span class="text-muted-foreground">세로</span><input type="number" min="2" max={videoHeight} bind:value={cropHeight} oninput={clampValues} class="h-10 w-full rounded-lg border border-input bg-background px-3" /></label>
			</div>
			<div class="flex flex-wrap items-center justify-between gap-2">
				<span class="text-xs text-muted-foreground">원본 {videoWidth} × {videoHeight} · {duration.toFixed(1)}초 · 회전 {rotation}°</span>
				<div class="flex gap-2">
					<OutlinedButton onclick={resetCrop}>전체 영상</OutlinedButton>
					<OutlinedButton onclick={rotateRight}><RotateCw size={16} strokeWidth={1.9} />회전</OutlinedButton>
				</div>
			</div>
		{:else}
			<p class="text-sm text-muted-foreground">영상 정보를 불러오는 중입니다.</p>
		{/if}
	</div>
	{#snippet footer()}
		<OutlinedButton disabled={saving} onclick={() => (open = false)}>취소</OutlinedButton>
		<PrimaryButton loading={saving} disabled={!duration} onclick={() => void save()}>편집 결과 저장</PrimaryButton>
	{/snippet}
</Modal>
