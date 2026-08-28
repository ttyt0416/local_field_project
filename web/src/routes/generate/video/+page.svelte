<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ImagePlus, Library, Music, Sparkles, Video } from '@lucide/svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import VideoMedia from '../../../../components/media/video.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { videoGenerationStore, type VideoLibraryAsset, type VideoMode } from '$lib/stores/video-generation.svelte';
	import { apiForm, apiJson } from '$lib/utils/api';

	type AssetRef = { kind: 'image' | 'audio'; file_id?: string; file_index?: number };
	type VideoStatus = {
		prompt_id: string;
		mode: VideoMode;
		status: string;
		video: { url: string } | null;
	};

	const modes: { value: VideoMode; label: string; description: string }[] = [
		{ value: 'i2v', label: 'I2V', description: '시작 이미지에서 영상 생성' },
		{ value: 'fl2v', label: 'FL2V', description: '첫·마지막 프레임 사이 생성' },
		{ value: 'r2v', label: 'R2V', description: 'reference 이미지·오디오 기반 생성' }
	];
	const inputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const fileClass = 'block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary';

	let ready = $state(false);
	let mode = $state<VideoMode>('i2v');
	let prompt = $state('');
	let width = $state(1344);
	let height = $state(768);
	let duration = $state(5);
	let seed = $state('');
	let firstFile = $state<File | null>(null);
	let lastFile = $state<File | null>(null);
	let referenceImageFiles = $state<File[]>([]);
	let referenceAudioFiles = $state<File[]>([]);
	let selectedFirst: VideoLibraryAsset | null = $state(null);
	let selectedLast: VideoLibraryAsset | null = $state(null);
	let selectedReferenceImages = $state<VideoLibraryAsset[]>([]);
	let selectedReferenceAudios = $state<VideoLibraryAsset[]>([]);
	let generating = $state(false);
	let status = $state('');
	let videoUrl = $state('');
	let error = $state('');
	let success = $state('');
	let active = true;

	onMount(() => {
		void initialize();
		return () => {
			active = false;
		};
	});

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		applyPendingSelection();
		ready = true;
	}

	function applyPendingSelection() {
		const pending = videoGenerationStore.consume();
		if (!pending) return;
		mode = pending.mode;
		selectedFirst = pending.firstFrame ?? null;
		selectedLast = pending.lastFrame ?? null;
		selectedReferenceImages = pending.referenceImages;
		selectedReferenceAudios = pending.referenceAudios;
	}

	function selectMode(next: VideoMode) {
		if (generating || mode === next) return;
		mode = next;
		firstFile = null;
		lastFile = null;
		referenceImageFiles = [];
		referenceAudioFiles = [];
		selectedFirst = null;
		selectedLast = null;
		selectedReferenceImages = [];
		selectedReferenceAudios = [];
	}

	function handleSingleFile(event: Event, target: 'first' | 'last') {
		if (!(event.currentTarget instanceof HTMLInputElement)) return;
		const file = event.currentTarget.files?.[0] ?? null;
		if (target === 'first') firstFile = file;
		else lastFile = file;
	}

	function handleMultipleFiles(event: Event, target: 'images' | 'audios') {
		if (!(event.currentTarget instanceof HTMLInputElement)) return;
		const files = Array.from(event.currentTarget.files ?? []);
		if (target === 'images') referenceImageFiles = files;
		else referenceAudioFiles = files;
	}

	function assetRef(kind: 'image' | 'audio', file: File | null, selected: VideoLibraryAsset | null, files: File[], form: FormData): AssetRef {
		if (file) {
			const index = files.length;
			files.push(file);
			form.append('files', file, file.name);
			return { kind, file_index: index };
		}
		if (selected) return { kind, file_id: selected.file_id };
		throw new Error(kind === 'image' ? '필요한 이미지를 선택해 주세요.' : '오디오를 선택해 주세요.');
	}

	function selectedAssetLabel(asset: VideoLibraryAsset | null, file: File | null) {
		return file?.name ?? asset?.filename ?? '선택되지 않음';
	}

	async function generate() {
		error = '';
		success = '';
		videoUrl = '';
		status = 'queued';
		if (!prompt.trim()) {
			error = '생성할 프롬프트를 입력해 주세요.';
			return;
		}
		const form = new FormData();
		const newFiles: File[] = [];
		try {
			const payload: Record<string, unknown> = {
				prompt: prompt.trim(),
				width: Number(width),
				height: Number(height),
				duration: Number(duration),
				seed: seed.trim() ? Number(seed) : null
			};
			if (mode === 'i2v') payload.first_frame = assetRef('image', firstFile, selectedFirst, newFiles, form);
			if (mode === 'fl2v') {
				payload.first_frame = assetRef('image', firstFile, selectedFirst, newFiles, form);
				payload.last_frame = assetRef('image', lastFile, selectedLast, newFiles, form);
			}
			if (mode === 'r2v') {
				payload.reference_images = [
					...selectedReferenceImages.map((asset) => ({ kind: 'image', file_id: asset.file_id })),
					...referenceImageFiles.map((file) => assetRef('image', file, null, newFiles, form))
				];
				payload.reference_audios = [
					...selectedReferenceAudios.map((asset) => ({ kind: 'audio', file_id: asset.file_id })),
					...referenceAudioFiles.map((file) => assetRef('audio', file, null, newFiles, form))
				];
			}
			form.append('payload', JSON.stringify(payload));
			generating = true;
			const accepted = await apiForm<{ prompt_id: string }>(`generation/video/${mode}`, form, { timeout: 120_000 });
			await poll(accepted.prompt_id);
		} catch (reason) {
			if (active) {
				error = reason instanceof Error ? reason.message : '영상 생성을 시작하지 못했습니다.';
				status = 'failed';
			}
		} finally {
			generating = false;
		}
	}

	async function poll(promptId: string) {
		for (let attempt = 0; attempt < 900 && active; attempt += 1) {
			const result = await apiJson<VideoStatus>(`generation/video/${mode}/${promptId}`, { timeout: 20_000 });
			status = result.status;
			if (result.status === 'completed') {
				if (!result.video?.url) throw new Error('생성된 영상을 찾을 수 없습니다.');
				videoUrl = result.video.url;
				success = '영상 생성이 완료되었습니다.';
				return;
			}
			if (result.status === 'failed') throw new Error('영상 생성에 실패했습니다.');
			await new Promise((resolve) => setTimeout(resolve, 2000));
		}
		if (active) throw new Error('영상 생성 상태 확인 시간이 초과되었습니다.');
	}

	function statusLabel(value: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패' }[value] ?? value;
	}
</script>

<svelte:head>
	<title>동영상 생성 · Local Field</title>
	<meta name="description" content="MiniMax H3 I2V, FL2V, R2V 동영상 생성" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="동영상 생성 페이지를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<Typography as="h1" variant="display">동영상 생성</Typography>
				<a href="/uploads" class="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground"><Library size={16} />콘텐츠 라이브러리</a>
			</div>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="video-result-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="video-result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div>
							{#if status}<Typography as="p" variant="muted" class="mt-1">상태: {statusLabel(status)}</Typography>{/if}
						</div>
						<Video size={22} class="text-primary" strokeWidth={1.8} />
					</div>
					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if videoUrl}
							<VideoMedia source={videoUrl} sourceType="server" preview={false} muted={false} class="min-h-[24rem] sm:min-h-[34rem]" />
						{:else if generating}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 sm:min-h-[34rem]"><LoadingSpinner size="lg" label="영상 생성 중" /><p class="text-sm text-muted-foreground">Storage 업로드와 영상 생성을 진행하고 있습니다.</p></div>
					{:else}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-3 px-6 text-center sm:min-h-[34rem]"><div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Video size={26} strokeWidth={1.7} /></div><p class="text-sm font-medium">아직 생성된 영상이 없습니다.</p><p class="max-w-sm text-xs leading-5 text-muted-foreground">콘텐츠를 선택하고 프롬프트를 입력한 뒤 생성 버튼을 눌러 주세요.</p></div>
						{/if}
					</div>
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="video-settings-title">
					<div id="video-settings-title"><Typography as="h2" variant="h2">동영상 설정</Typography></div>
					<div class="mt-5 grid grid-cols-3 rounded-xl border border-border p-1" role="tablist" aria-label="동영상 생성 방식">
						{#each modes as item}
							<button type="button" role="tab" aria-selected={mode === item.value} onclick={() => selectMode(item.value)} class={`rounded-lg px-2 py-2 text-sm font-semibold transition ${mode === item.value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}>{item.label}</button>
						{/each}
					</div>
					<p class="mt-2 text-xs text-muted-foreground">{modes.find((item) => item.value === mode)?.description}</p>

					<form class="mt-5 space-y-5 pb-24 sm:pb-0" onsubmit={(event) => { event.preventDefault(); void generate(); }}>
						<label class="block space-y-2" for="video-prompt"><span class="text-sm font-medium">프롬프트</span><textarea id="video-prompt" bind:value={prompt} rows="6" required class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="장면, 움직임, 카메라, 음성을 설명해 주세요."></textarea></label>

						{#if mode === 'i2v'}
							<label class="block space-y-2" for="i2v-image"><span class="text-sm font-medium">시작 이미지</span><input id="i2v-image" type="file" accept="image/*" class={fileClass} onchange={(event) => handleSingleFile(event, 'first')} /><span class="block truncate text-xs text-muted-foreground">{selectedAssetLabel(selectedFirst, firstFile)} · 파일은 생성 시 업로드됩니다.</span></label>
						{:else if mode === 'fl2v'}
							<div class="space-y-4"><label class="block space-y-2" for="fl2v-first"><span class="text-sm font-medium">첫 프레임</span><input id="fl2v-first" type="file" accept="image/*" class={fileClass} onchange={(event) => handleSingleFile(event, 'first')} /><span class="block truncate text-xs text-muted-foreground">{selectedAssetLabel(selectedFirst, firstFile)}</span></label><label class="block space-y-2" for="fl2v-last"><span class="text-sm font-medium">마지막 프레임</span><input id="fl2v-last" type="file" accept="image/*" class={fileClass} onchange={(event) => handleSingleFile(event, 'last')} /><span class="block truncate text-xs text-muted-foreground">{selectedAssetLabel(selectedLast, lastFile)}</span></label><p class="text-xs text-muted-foreground">새 파일은 생성 버튼을 누를 때만 Storage에 저장됩니다.</p></div>
						{:else}
							<div class="space-y-4"><label class="block space-y-2" for="r2v-images"><span class="text-sm font-medium">Reference 이미지 · 최대 9개</span><input id="r2v-images" type="file" accept="image/*" multiple class={fileClass} onchange={(event) => handleMultipleFiles(event, 'images')} /><span class="block truncate text-xs text-muted-foreground">{selectedReferenceImages.length + referenceImageFiles.length}개 선택</span></label><label class="block space-y-2" for="r2v-audios"><span class="text-sm font-medium">Reference 오디오 · 최대 3개</span><input id="r2v-audios" type="file" accept="audio/*" multiple class={fileClass} onchange={(event) => handleMultipleFiles(event, 'audios')} /><span class="block truncate text-xs text-muted-foreground">{selectedReferenceAudios.length + referenceAudioFiles.length}개 선택</span></label><p class="text-xs text-muted-foreground">라이브러리에서 기존 콘텐츠를 추가하거나 새 파일을 선택할 수 있습니다. 새 파일은 생성 시에만 업로드됩니다.</p></div>
						{/if}
						<a href="/uploads" class="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"><Library size={16} />업로드·생성 콘텐츠에서 선택</a>

						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-width"><span class="text-sm font-medium">가로</span><input id="video-width" type="number" min="32" max="1344" step="32" bind:value={width} class={inputClass} /></label><label class="block space-y-2" for="video-height"><span class="text-sm font-medium">세로</span><input id="video-height" type="number" min="32" max="1344" step="32" bind:value={height} class={inputClass} /></label></div>
						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-duration"><span class="text-sm font-medium">길이(초)</span><input id="video-duration" type="number" min="1" max="15" step="0.1" bind:value={duration} class={inputClass} /></label><label class="block space-y-2" for="video-seed"><span class="text-sm font-medium">Seed · 선택</span><input id="video-seed" type="number" min="0" bind:value={seed} class={inputClass} /></label></div>

						<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"><PrimaryButton type="submit" loading={generating} disabled={!prompt.trim()} class="w-full"><Sparkles size={17} strokeWidth={1.9} /><span>{generating ? '생성 중' : '동영상 생성'}</span></PrimaryButton></div>
					</form>
				</section>
			</div>
		</div>
	</Layout>
	{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="동영상 생성 실패" message={error} onclose={() => (error = '')} /></div>{:else if success}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="생성 완료" message={success} onclose={() => (success = '')} /></div>{/if}
{/if}
