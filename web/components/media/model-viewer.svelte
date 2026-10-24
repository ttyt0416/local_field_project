<script lang="ts">
	import { browser } from '$app/environment';
	import LoadingShimmer from '../loadings/loading-shimmer.svelte';
	import Toast from '../feedback/toast.svelte';
	import { apiBlob } from '$lib/utils/api';
	import { inspectRig, type RigInspection } from '$lib/utils/rig-inspection';
	import OutlinedButton from '../buttons/outlined-button.svelte';

	type MediaSource = string | Blob;
	type ModelViewerElement = HTMLElement & {
		cameraControls?: boolean;
		autoRotate?: boolean;
		queryHotspot?: (name: string) => { canvasPosition: { x: number; y: number; z: number } } | null;
	};
	type Props = {
		source: MediaSource;
		alt?: string;
		sourceType?: 'local' | 'server';
		cameraControls?: boolean;
		autoRotate?: boolean;
		poster?: string;
		shadowIntensity?: number;
		exposure?: number;
		inspectRigging?: boolean;
		class?: string;
	};

	let {
		source,
		alt = '3D 모델',
		sourceType = 'local',
		cameraControls = true,
		autoRotate = false,
		poster,
		shadowIntensity = 1,
		exposure = 1,
		inspectRigging = false,
		class: className = ''
	}: Props = $props();

	let sourceUrl = $state('');
	let loaded = $state(false);
	let failed = $state(false);
	let error = $state('');
	let modelViewer = $state<ModelViewerElement>();
	let rig = $state<RigInspection | null>(null);
	let showRig = $state(true);
	let projected = $state<{ id: number; parent: number | null; name: string; x: number; y: number; visible: boolean }[]>([]);
	let rigLines = $derived(projected.flatMap((point) => {
		const parent = projected.find((item) => item.id === point.parent);
		return parent?.visible && point.visible ? [{ from: parent, to: point }] : [];
	}));
	const modelViewerTag = 'model-viewer';
	let isServerSource = $derived(sourceType === 'server' || (typeof source === 'string' && /^(https?:)?\/\//.test(source)));

	$effect(() => {
		if (browser) {
			void import('@google/model-viewer').catch(() => {
				failed = true;
				error = '3D 뷰어를 불러오지 못했습니다.';
			});
		}
	});

	$effect(() => {
		const inspect = inspectRigging;
		loaded = false;
		failed = false;
		error = '';
		rig = null;
		showRig = true;
		if (browser && typeof source === 'string' && isServerSource) {
			let cancelled = false;
			let objectUrl = '';
			sourceUrl = '';
			void apiBlob(source, { timeout: 120_000 })
				.then((blob) => {
					if (cancelled) return;
					objectUrl = URL.createObjectURL(blob);
					sourceUrl = objectUrl;
					if (inspect) readRig(blob, () => !cancelled);
				})
				.catch((reason) => {
					if (cancelled) return;
					failed = true;
					error = reason instanceof Error ? reason.message : '3D 모델을 불러오지 못했습니다.';
				});
			return () => {
				cancelled = true;
				if (objectUrl) URL.revokeObjectURL(objectUrl);
			};
		}
		if (typeof source === 'string') {
			sourceUrl = source;
			return;
		}
		if (!browser) {
			sourceUrl = '';
			return;
		}
		const objectUrl = URL.createObjectURL(source);
		sourceUrl = objectUrl;
		let cancelled = false;
		if (inspect) readRig(source, () => !cancelled);
		return () => {
			cancelled = true;
			URL.revokeObjectURL(objectUrl);
		};
	});

	function readRig(blob: Blob, isCurrent: () => boolean) {
		void inspectRig(blob).then((result) => {
			if (isCurrent()) rig = result;
		}).catch(() => {
			if (isCurrent()) error = '모델은 열었지만 뼈대 정보를 읽지 못했습니다.';
		});
	}

	$effect(() => {
		if (!browser || !loaded || !inspectRigging || !showRig || !rig || !modelViewer) {
			projected = [];
			return;
		}
		const viewer = modelViewer;
		const joints = rig.joints;
		let frame = 0;
		function update() {
			projected = joints.flatMap((joint) => {
				const point = viewer.queryHotspot?.(`hotspot-rig-${joint.id}`)?.canvasPosition;
				return point ? [{ id: joint.id, parent: joint.parent, name: joint.name, x: point.x, y: point.y, visible: point.z >= -1 && point.z <= 1 }] : [];
			});
			frame = requestAnimationFrame(update);
		}
		frame = requestAnimationFrame(update);
		return () => cancelAnimationFrame(frame);
	});

	$effect(() => {
		if (!modelViewer) return;
		modelViewer.cameraControls = cameraControls;
		modelViewer.autoRotate = autoRotate;
	});
</script>

<div class={`relative overflow-hidden rounded-xl bg-muted ${className}`}>
	{#if isServerSource && !loaded && !failed}
		<LoadingShimmer class="absolute inset-0 z-10 h-full w-full rounded-none" label="3D 모델 불러오는 중" />
	{/if}

	{#if failed}
		<div class="flex min-h-64 items-center justify-center px-4 text-center text-sm text-muted-foreground" role="alert">
			3D 모델을 불러올 수 없습니다.
		</div>
	{:else if sourceUrl}
		<svelte:element
			this={modelViewerTag}
			bind:this={modelViewer}
			src={sourceUrl}
			alt={alt}
			poster={poster}
			camera-controls={cameraControls ? '' : undefined}
			auto-rotate={autoRotate ? '' : undefined}
			interaction-prompt="auto"
			shadow-intensity={shadowIntensity}
			exposure={exposure}
			loading="lazy"
			onload={() => (loaded = true)}
			onerror={() => (failed = true)}
			class={`block h-full min-h-64 w-full bg-muted transition-opacity ${isServerSource && !loaded ? 'opacity-0' : 'opacity-100'}`}
		>
			{#if inspectRigging && rig}
				{#each rig.joints as joint (joint.id)}
					<span slot={`hotspot-rig-${joint.id}`} data-position={joint.position.map((value) => `${value}m`).join(' ')} style="display:none;"></span>
				{/each}
			{/if}
		</svelte:element>
	{/if}

	{#if inspectRigging && loaded && rig}
		<div class="absolute left-3 top-3 z-20 max-w-[calc(100%-1.5rem)] rounded-xl border border-border bg-card/95 p-3 shadow-sm">
			<div class="flex flex-wrap items-center gap-3">
				<OutlinedButton disabled={!rig.joints.length} active={showRig} onclick={() => (showRig = !showRig)}>{showRig ? '뼈대 숨기기' : '뼈대 보기'}</OutlinedButton>
				<p class="text-xs text-foreground">관절 {rig.joints.length}개 · 스킨 메시 {rig.skinnedMeshes}개</p>
			</div>
			<p class="mt-2 text-xs text-muted-foreground">{rig.joints.length ? '주황 점은 관절, 청록 선은 뼈대 연결입니다.' : '이 파일에서 사용 중인 뼈대를 찾지 못했습니다.'}</p>
			<p class="mt-1 text-xs text-muted-foreground">기본 자세 표시 · {rig.animations ? `애니메이션 ${rig.animations}개 포함` : '애니메이션 없음'}</p>
		</div>
		{#if showRig && projected.length}
			<svg class="pointer-events-none absolute inset-0 z-10 h-full w-full" role="img" aria-label={`리깅 뼈대: 관절 ${rig.joints.length}개`}>
				{#each rigLines as line (line.to.id)}
					<line x1={line.from.x} y1={line.from.y} x2={line.to.x} y2={line.to.y} stroke="#0f172a" stroke-width="5" />
					<line x1={line.from.x} y1={line.from.y} x2={line.to.x} y2={line.to.y} stroke="#22d3ee" stroke-width="2.5" />
				{/each}
				{#each projected.filter((point) => point.visible) as point (point.id)}
					<circle cx={point.x} cy={point.y} r="4" fill="#fb923c" stroke="#0f172a" stroke-width="1.5"><title>{point.name}</title></circle>
				{/each}
			</svg>
		{/if}
	{/if}
</div>

{#if error}
	<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="3D 모델 조회 실패" message={error} onclose={() => (error = '')} /></div>
{/if}
