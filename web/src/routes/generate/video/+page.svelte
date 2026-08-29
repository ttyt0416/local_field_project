<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { AudioLines, ChevronLeft, ChevronRight, Database, HardDrive, Image as ImageIcon, Sparkles, Video } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';

	import Modal from '../../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import SearchBar from '../../../../components/inputs/searchbar.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import VideoMedia from '../../../../components/media/video.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { videoGenerationStore, type VideoLibraryAsset, type VideoMode } from '$lib/stores/video-generation.svelte';
	import { apiForm, apiJson } from '$lib/utils/api';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';

	type AssetRef = { kind: 'image' | 'audio' | 'video'; file_id?: string; file_index?: number };
	type SelectionTarget = 'first' | 'last' | 'images' | 'videos' | 'audios';
	type SelectionSource = 'device' | 'stored';
	type StoredMediaAsset = VideoLibraryAsset & { source_type: string; created_at: string };
	type StoredMediaPage = {
		items: StoredMediaAsset[];
		page: number;
		page_size: number;
		total_count: number;
		total_pages: number;
	};
	type StoredSort = 'latest' | 'oldest' | 'name';
	type VideoPromptLanguage = 'ko' | 'en' | 'ja';
	const modes: { value: VideoMode; label: string; description: string }[] = [
		{ value: 'i2v', label: 'I2V', description: '시작 이미지에서 영상 생성' },
		{ value: 'fl2v', label: 'FL2V', description: '첫·마지막 프레임 사이 생성' },
		{ value: 'r2v', label: 'R2V', description: '참조 이미지·동영상·오디오 기반 생성' }
];
	const promptLanguageOptions: { value: VideoPromptLanguage; label: string }[] = [
		{ value: 'ko', label: '한글' },
		{ value: 'en', label: '영어' },
		{ value: 'ja', label: '일어' }
	];
	const inputClass = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20';
	const fileClass = 'block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary';

	let ready = $state(false);
	let mode = $state<VideoMode>('i2v');
	let prompt = $state('');
	let promptEnhancementEnabled = $state(false);
	let improvedPrompt = $state('');
	let promptOutputLanguages = $state<VideoPromptLanguage[]>(['en']);
	let enhancingPrompt = $state(false);
	let width = $state(1344);
	let height = $state(768);
	let duration = $state(5);
	let seed = $state('');
	let randomSeed = $state(true);
	let firstFile = $state<File | null>(null);
	let lastFile = $state<File | null>(null);
	let referenceImageFiles = $state<File[]>([]);
	let referenceVideoFiles = $state<File[]>([]);
	let referenceAudioFiles = $state<File[]>([]);
	let selectedFirst: VideoLibraryAsset | null = $state(null);
	let selectedLast: VideoLibraryAsset | null = $state(null);
	let selectedReferenceImages = $state<VideoLibraryAsset[]>([]);
	let selectedReferenceVideos = $state<VideoLibraryAsset[]>([]);
	let selectedReferenceAudios = $state<VideoLibraryAsset[]>([]);
	let generating = $state(false);
	let uploading = $state(false);
	let status = $state('');
	let progress = $state(0);
	let queuePosition = $state<number | null>(null);
	let videoUrl = $state('');
	let error = $state('');
	let success = $state('');
	let active = true;
	let videoJobKey = $state('');
	let selectionOpen = $state(false);
	let selectionTarget = $state<SelectionTarget | null>(null);
	let selectionSource = $state<SelectionSource>('device');
	let storedAssets = $state<StoredMediaAsset[]>([]);
	let storedLoading = $state(false);
	let storedSearch = $state('');
	let storedSort = $state<StoredSort>('latest');
	let storedPage = $state(1);
	let storedTotalPages = $state(0);
	let storedSelectedIds = $state<string[]>([]);
	let storedSelectedAssets = $state<StoredMediaAsset[]>([]);
	let storedRequestId = 0;
	let selectionKind = $derived(
		selectionTarget === 'videos' ? 'video' : selectionTarget === 'audios' ? 'audio' : 'image'
	);
	let selectionMultiple = $derived(selectionTarget === 'images' || selectionTarget === 'videos' || selectionTarget === 'audios');
	let selectionMax = $derived(selectionTarget === 'images' ? 9 : selectionMultiple ? 3 : 1);
	let selectionTitle = $derived(
		selectionTarget === 'first'
			? '시작 이미지 선택'
			: selectionTarget === 'last'
				? '마지막 프레임 선택'
				: selectionTarget === 'images'
					? '참조 이미지 선택'
					: selectionTarget === 'videos'
						? '참조 동영상 선택'
						: '참조 오디오 선택'
	);

	onMount(() => {
		void initialize();
		return () => {
			active = false;
		};
	});

	$effect(() => {
		const job = videoJobKey ? generationJobStore.jobs[videoJobKey] : undefined;
		if (!job) return;
		status = job.status;
		progress = job.progress;
		queuePosition = job.queuePosition;
		videoUrl = job.videoUrl ?? '';
		if (job.status === 'completed') success = '영상 생성이 완료되었습니다.';
		if (job.status === 'failed') error = job.error ?? '영상 생성에 실패했습니다.';
	});

	async function initialize() {
		resetResult();
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		await generationJobStore.initialize();
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
		selectedReferenceVideos = pending.referenceVideos;
		selectedReferenceAudios = pending.referenceAudios;
	}

	function selectMode(next: VideoMode) {
		if (generating || mode === next) return;
		mode = next;
		improvedPrompt = '';
		firstFile = null;
		lastFile = null;
		referenceImageFiles = [];
		referenceVideoFiles = [];
		referenceAudioFiles = [];
		selectedFirst = null;
		selectedLast = null;
		selectedReferenceImages = [];
		selectedReferenceVideos = [];
		selectedReferenceAudios = [];
	}

	function togglePromptLanguage(language: VideoPromptLanguage, checked: boolean) {
		if (checked) {
			if (!promptOutputLanguages.includes(language)) promptOutputLanguages = [...promptOutputLanguages, language];
			improvedPrompt = '';
			return;
		}
		if (promptOutputLanguages.length === 1) {
			error = '출력 언어를 하나 이상 선택해 주세요.';
			return;
		}
		promptOutputLanguages = promptOutputLanguages.filter((value) => value !== language);
		improvedPrompt = '';
	}


	function assetRef(kind: 'image' | 'audio' | 'video', file: File | null, selected: VideoLibraryAsset | null, files: File[], form: FormData): AssetRef {
		if (file) {
			const index = files.length;
			files.push(file);
			form.append('files', file, file.name);
			return { kind, file_index: index };
		}
		if (selected) return { kind, file_id: selected.file_id };
		throw new Error(kind === 'image' ? '필요한 이미지를 선택해 주세요.' : kind === 'video' ? '동영상을 선택해 주세요.' : '오디오를 선택해 주세요.');
	}

	function imageSourceType(url: string): 'external' | 'server' {
		return /^(https?:)?\/\//.test(url) ? 'external' : 'server';
	}

	function openSelection(target: SelectionTarget) {
		if (generating) return;
		selectionTarget = target;
		selectionSource = 'device';
		storedAssets = [];
		storedSearch = '';
		storedSort = 'latest';
		storedPage = 1;
		storedTotalPages = 0;
		storedSelectedIds = [];
		storedSelectedAssets = [];
		selectionOpen = true;
	}

	function selectSelectionSource(source: SelectionSource) {
		selectionSource = source;
		if (source === 'stored') {
			storedPage = 1;
			storedSelectedIds = [];
			storedSelectedAssets = [];
			void loadStoredAssets(1);
		}
	}

	function currentSelectionCount() {
		if (selectionTarget === 'images') return selectedReferenceImages.length + referenceImageFiles.length;
		if (selectionTarget === 'videos') return selectedReferenceVideos.length + referenceVideoFiles.length;
		if (selectionTarget === 'audios') return selectedReferenceAudios.length + referenceAudioFiles.length;
		return 0;
	}

	async function loadStoredAssets(requestedPage = storedPage) {
		if (!selectionTarget) return;
		const requestId = ++storedRequestId;
		storedLoading = true;
		try {
			const params = new URLSearchParams({
				include_generated: 'true',
				media_kind: selectionKind,
				search: storedSearch,
				sort: storedSort,
				page: String(requestedPage)
			});
			const result = await apiJson<StoredMediaPage>(`uploads?${params.toString()}`);
			if (requestId === storedRequestId) {
				storedAssets = result.items;
				storedPage = result.page;
				storedTotalPages = result.total_pages;
			}
		} catch (reason) {
			if (requestId === storedRequestId) error = reason instanceof Error ? reason.message : '저장된 콘텐츠를 불러오지 못했습니다.';
		} finally {
			if (requestId === storedRequestId) storedLoading = false;
		}
	}

	function changeStoredFilter() {
		storedSelectedIds = [];
		storedSelectedAssets = [];
		void loadStoredAssets(1);
	}

	function changeStoredPage(nextPage: number) {
		if (nextPage < 1 || nextPage > storedTotalPages) return;
		void loadStoredAssets(nextPage);
	}

	function handleDeviceSelection(event: Event) {
		if (!(event.currentTarget instanceof HTMLInputElement) || !selectionTarget) return;
		const available = selectionMultiple ? Math.max(selectionMax - currentSelectionCount(), 0) : 1;
		const files = Array.from(event.currentTarget.files ?? []).slice(0, available);
		if (!files.length) return;
		if (selectionTarget === 'first') {
			firstFile = files[0];
			selectedFirst = null;
		} else if (selectionTarget === 'last') {
			lastFile = files[0];
			selectedLast = null;
		} else if (selectionTarget === 'images') {
			referenceImageFiles = [...referenceImageFiles, ...files].slice(0, selectionMax);
		} else if (selectionTarget === 'videos') {
			referenceVideoFiles = [...referenceVideoFiles, ...files].slice(0, selectionMax);
		} else {
			referenceAudioFiles = [...referenceAudioFiles, ...files].slice(0, selectionMax);
		}
		selectionOpen = false;
	}

	function toggleStoredAsset(asset: StoredMediaAsset) {
		if (!selectionMultiple) {
			applyStoredAssets([asset]);
			return;
		}
		if (storedSelectedIds.includes(asset.file_id)) {
			storedSelectedIds = storedSelectedIds.filter((fileId) => fileId !== asset.file_id);
			storedSelectedAssets = storedSelectedAssets.filter((item) => item.file_id !== asset.file_id);
			return;
		}
		if (currentSelectionCount() + storedSelectedIds.length >= selectionMax) {
			error = `최대 ${selectionMax}개까지 선택할 수 있습니다.`;
			return;
		}
		storedSelectedIds = [...storedSelectedIds, asset.file_id];
		storedSelectedAssets = [...storedSelectedAssets, asset];
	}

	function applyStoredAssets(assetsToApply: StoredMediaAsset[]) {
		if (!selectionTarget) return;
		const existing = currentSelectionCount();
		const available = selectionMultiple ? Math.max(selectionMax - existing, 0) : 1;
		const existingIds = selectionTarget === 'images' ? selectedReferenceImages.map((asset) => asset.file_id) : selectionTarget === 'videos' ? selectedReferenceVideos.map((asset) => asset.file_id) : selectedReferenceAudios.map((asset) => asset.file_id);
		const assetsToUse = assetsToApply.filter((asset) => !existingIds.includes(asset.file_id)).slice(0, available);
		if (selectionTarget === 'first') {
			selectedFirst = assetsToUse[0] ?? null;
			firstFile = null;
		} else if (selectionTarget === 'last') {
			selectedLast = assetsToUse[0] ?? null;
			lastFile = null;
		} else if (selectionTarget === 'images') {
			selectedReferenceImages = [
				...selectedReferenceImages,
				...assetsToUse.filter((asset) => !selectedReferenceImages.some((item) => item.file_id === asset.file_id))
			].slice(0, selectionMax);
		} else if (selectionTarget === 'videos') {
			selectedReferenceVideos = [
				...selectedReferenceVideos,
				...assetsToUse.filter((asset) => !selectedReferenceVideos.some((item) => item.file_id === asset.file_id))
			].slice(0, selectionMax);
		} else {
			selectedReferenceAudios = [
				...selectedReferenceAudios,
				...assetsToUse.filter((asset) => !selectedReferenceAudios.some((item) => item.file_id === asset.file_id))
			].slice(0, selectionMax);
		}
		storedSelectedIds = [];
		storedSelectedAssets = [];
		selectionOpen = false;
	}

	function confirmStoredSelection() {
		applyStoredAssets(storedSelectedAssets);
	}

	function storedSourceLabel(asset: StoredMediaAsset) {
		return asset.source_type === 'image_generation' ? '생성 이미지' : asset.source_type === 'video_generation' ? '생성 동영상' : '업로드 콘텐츠';
	}

	async function enhancePrompt() {
		error = '';
		if (!prompt.trim()) {
			error = '개선할 프롬프트를 입력해 주세요.';
			return;
		}
		if (!promptOutputLanguages.length) {
			error = '출력 언어를 하나 이상 선택해 주세요.';
			return;
		}
		enhancingPrompt = true;
		try {
			const result = await apiJson<{ improved_prompt: { contents: string } }>('generation/video/enhance-prompt', {
				method: 'POST',
				timeout: 600_000,
				json: {
					prompt: prompt.trim(),
					mode,
					duration: Number(duration),
					prompt_output_languages: promptOutputLanguages
				}
			});
			improvedPrompt = result.improved_prompt.contents;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '프롬프트를 개선하지 못했습니다.';
		} finally {
			enhancingPrompt = false;
		}
	}

	async function generate() {
		videoJobKey = '';
		error = '';
		success = '';
		videoUrl = '';
		status = 'queued';
		if (!prompt.trim()) {
			error = '생성할 프롬프트를 입력해 주세요.';
			return;
		}
		if (!promptOutputLanguages.length) {
			error = '출력 언어를 하나 이상 선택해 주세요.';
			return;
		}
		if (promptEnhancementEnabled && !improvedPrompt.trim()) {
			error = '개선된 프롬프트를 먼저 생성해 주세요.';
			return;
		}
		if (!randomSeed && !seed.trim()) {
			error = '시드를 입력하거나 무작위 시드를 선택해 주세요.';
			return;
		}
		const form = new FormData();
		const newFiles: File[] = [];
		try {
			const payload: Record<string, unknown> = {
				prompt: prompt.trim(),
				prompt_enhancement_enabled: promptEnhancementEnabled,
				improved_prompt: promptEnhancementEnabled ? improvedPrompt.trim() : null,
				prompt_output_languages: promptOutputLanguages,
				width: Number(width),
				height: Number(height),
				duration: Number(duration),
				seed: randomSeed ? null : seed.trim() || null
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
				payload.reference_videos = [
					...selectedReferenceVideos.map((asset) => ({ kind: 'video', file_id: asset.file_id })),
					...referenceVideoFiles.map((file) => assetRef('video', file, null, newFiles, form))
				];
				payload.reference_audios = [
					...selectedReferenceAudios.map((asset) => ({ kind: 'audio', file_id: asset.file_id })),
					...referenceAudioFiles.map((file) => assetRef('audio', file, null, newFiles, form))
				];
			}
			form.append('payload', JSON.stringify(payload));
			generating = true;
			uploading = newFiles.length > 0;
			const accepted = await apiForm<{ prompt_id: string; client_id: string; generation_id: string }>(`generation/video/${mode}`, form, { timeout: 120_000 });
			videoJobKey = generationJobStore.track({
				kind: 'video',
				promptId: accepted.prompt_id,
				clientId: accepted.client_id,
				generationId: accepted.generation_id,
				mode
			});
			await generationJobStore.waitForTerminal(videoJobKey);
		} catch (reason) {
			if (active) {
				error = reason instanceof Error ? reason.message : '영상 생성을 시작하지 못했습니다.';
				status = 'failed';
			}
		} finally {
			uploading = false;
			generating = false;
		}
	}

	function statusLabel(value: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패' }[value] ?? value;
	}

	function resetResult() {
		status = '';
		progress = 0;
		queuePosition = null;
		videoUrl = '';
		error = '';
		success = '';
		videoJobKey = '';
		generating = false;
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
			</div>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="video-result-title">
					<div class="flex items-center justify-between gap-4">
						<div>
							<div id="video-result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div>
							{#if status}<Typography as="p" variant="muted" class="mt-1">상태: {statusLabel(status)}{#if status === 'queued' || status === 'processing'} · {Math.round(progress)}%{/if}{#if status === 'queued' && queuePosition !== null} · 대기 {queuePosition}번째{/if}</Typography>{/if}
						</div>
						<Video size={22} class="text-primary" strokeWidth={1.8} />
					</div>
					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if videoUrl}
							<VideoMedia source={videoUrl} sourceType="server" preview={false} muted={false} class="min-h-[24rem] sm:min-h-[34rem]" />
						{:else if generating}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 sm:min-h-[34rem]"><LoadingSpinner size="lg" label={uploading ? '파일 업로드 중' : '영상 생성 중'} /><p class="text-sm text-muted-foreground">{uploading ? '파일을 업로드를 진행하고 있습니다.' : '영상 생성중입니다.'}</p>{#if !uploading}<p class="text-2xl font-semibold tabular-nums text-primary">{Math.round(progress)}%</p>{/if}</div>
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
						<div class="space-y-3">
							<div class="flex items-center justify-between gap-3">
								<label for="video-prompt" class="text-sm font-medium">프롬프트</label>
								<div class="flex items-center gap-2">
									<label for="video-prompt-enhancement-enabled" class="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg border border-border px-3 text-xs font-semibold text-muted-foreground transition hover:bg-muted">
										<input id="video-prompt-enhancement-enabled" type="checkbox" bind:checked={promptEnhancementEnabled} class="peer sr-only" />
										<span>프롬프트 개선</span>
										<span class="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground peer-checked:bg-primary/10 peer-checked:text-primary">{promptEnhancementEnabled ? 'ON' : 'OFF'}</span>
									</label>
									<OutlinedButton
										type="button"
										loading={enhancingPrompt}
										disabled={generating || !prompt.trim() || !promptEnhancementEnabled || !promptOutputLanguages.length}
										class="min-h-9 px-3 text-xs"
										onclick={() => void enhancePrompt()}
									>
										<Sparkles size={14} strokeWidth={1.9} />
										<span>{enhancingPrompt ? '개선 중' : '프롬프트 개선'}</span>
									</OutlinedButton>
								</div>
							</div>
							<textarea id="video-prompt" bind:value={prompt} oninput={() => (improvedPrompt = '')} rows="6" required class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="장면, 움직임, 카메라, 음성을 설명해 주세요."></textarea>
							{#if promptEnhancementEnabled}
								<div class="space-y-3 rounded-xl border border-primary/20 bg-primary/5 p-3">
									<div class="space-y-2">
										<div class="flex items-center justify-between gap-3"><span class="text-sm font-medium">출력 언어</span><span class="text-xs text-muted-foreground">복수 선택 가능</span></div>
										<div class="grid gap-2 sm:grid-cols-3">
											{#each promptLanguageOptions as language}
												<label class="flex cursor-pointer items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm transition hover:bg-muted">
													<input type="checkbox" checked={promptOutputLanguages.includes(language.value)} onchange={(event) => togglePromptLanguage(language.value, (event.currentTarget as HTMLInputElement).checked)} class="size-4 accent-primary" />
													<span>{language.label}</span>
												</label>
											{/each}
										</div>
									</div>
									<label class="block space-y-2" for="video-improved-prompt">
										<span class="text-sm font-medium">개선된 프롬프트</span>
										<textarea id="video-improved-prompt" bind:value={improvedPrompt} rows="9" disabled={enhancingPrompt} class="w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="개선된 프롬프트가 여기에 표시됩니다."></textarea>
									</label>
								</div>
							{/if}
						</div>

						{#if mode === 'i2v'}
							<div class="space-y-3">
								<OutlinedButton class="w-full" onclick={() => openSelection('first')}><HardDrive size={16} />시작 이미지 선택</OutlinedButton>
								{#if firstFile || selectedFirst?.url}
									<div class="grid grid-cols-2 gap-3">
										<div class="overflow-hidden rounded-xl border border-border bg-muted">
											{#if firstFile}
												<ImageMedia source={firstFile} sourceType="local" alt="선택한 시작 이미지" class="h-full" />
											{:else if selectedFirst?.url}
												<ImageMedia source={selectedFirst.url} sourceType={imageSourceType(selectedFirst.url)} alt="선택한 시작 이미지" class="h-full" />
											{/if}
											<p class="border-t border-border px-3 py-2 text-xs font-medium">시작 이미지</p>
										</div>
									</div>
								{/if}
							</div>
						{:else if mode === 'fl2v'}
							<div class="space-y-4">
								<div class="grid grid-cols-2 gap-4">
									<div class="space-y-3">
										<OutlinedButton class="w-full" onclick={() => openSelection('first')}><HardDrive size={16} />첫 프레임 선택</OutlinedButton>
										{#if firstFile || selectedFirst?.url}
											<div class="overflow-hidden rounded-xl border border-border bg-muted">
												{#if firstFile}
													<ImageMedia source={firstFile} sourceType="local" alt="선택한 첫 프레임" class="h-full" />
												{:else if selectedFirst?.url}
													<ImageMedia source={selectedFirst.url} sourceType={imageSourceType(selectedFirst.url)} alt="선택한 첫 프레임" class="h-full" />
												{/if}
												<p class="border-t border-border px-3 py-2 text-xs font-medium">첫 프레임</p>
											</div>
										{/if}
									</div>
									<div class="space-y-3">
										<OutlinedButton class="w-full" onclick={() => openSelection('last')}><HardDrive size={16} />마지막 프레임 선택</OutlinedButton>
										{#if lastFile || selectedLast?.url}
											<div class="overflow-hidden rounded-xl border border-border bg-muted">
												{#if lastFile}
													<ImageMedia source={lastFile} sourceType="local" alt="선택한 마지막 프레임" class="h-full" />
												{:else if selectedLast?.url}
													<ImageMedia source={selectedLast.url} sourceType={imageSourceType(selectedLast.url)} alt="선택한 마지막 프레임" class="h-full" />
												{/if}
												<p class="border-t border-border px-3 py-2 text-xs font-medium">마지막 프레임</p>
											</div>
										{/if}
									</div>
								</div>
							</div>
						{:else}
							<div class="space-y-5">
								<div class="space-y-3">
									<OutlinedButton class="w-full" onclick={() => openSelection('images')}><HardDrive size={16} />참조 이미지 추가</OutlinedButton>
									{#if selectedReferenceImages.length + referenceImageFiles.length > 0}
										<div class="grid grid-cols-2 gap-3">
											{#each selectedReferenceImages as asset, index (asset.file_id)}
												<div class="overflow-hidden rounded-xl border border-border bg-muted">
													{#if asset.url}
														<ImageMedia source={asset.url} sourceType={imageSourceType(asset.url)} alt={`참조 이미지 ${index + 1}`} class="h-full" />
													{:else}
														<div class="flex min-h-32 items-center justify-center"><ImageIcon size={30} class="text-primary" /></div>
													{/if}
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 이미지 {index + 1}</p>
												</div>
											{/each}
											{#each referenceImageFiles as file, index}
												<div class="overflow-hidden rounded-xl border border-border bg-muted">
													<ImageMedia source={file} sourceType="local" alt={`참조 이미지 ${selectedReferenceImages.length + index + 1}`} class="h-full" />
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 이미지 {selectedReferenceImages.length + index + 1}</p>
												</div>
											{/each}
										</div>
									{/if}
								</div>

								<div class="space-y-3">
									<OutlinedButton class="w-full" onclick={() => openSelection('videos')}><HardDrive size={16} />참조 동영상 추가</OutlinedButton>
									{#if selectedReferenceVideos.length + referenceVideoFiles.length > 0}
										<div class="grid grid-cols-2 gap-3">
											{#each selectedReferenceVideos as asset, index (asset.file_id)}
												<div class="overflow-hidden rounded-xl border border-border bg-muted">
													{#if asset.url}
														<VideoMedia source={asset.url} sourceType="server" preview={false} muted={true} class="h-full" />
													{:else}
														<div class="flex min-h-32 items-center justify-center"><Video size={30} class="text-primary" /></div>
													{/if}
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 동영상 {index + 1}</p>
												</div>
											{/each}
											{#each referenceVideoFiles as file, index}
												<div class="overflow-hidden rounded-xl border border-border bg-muted">
													<VideoMedia source={file} preview={false} muted={true} class="h-full" />
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 동영상 {selectedReferenceVideos.length + index + 1}</p>
												</div>
											{/each}
										</div>
									{/if}
								</div>

								<div class="space-y-3">
									<OutlinedButton class="w-full" onclick={() => openSelection('audios')}><HardDrive size={16} />참조 오디오 추가</OutlinedButton>
									{#if selectedReferenceAudios.length + referenceAudioFiles.length > 0}
										<div class="grid grid-cols-2 gap-3">
											{#each selectedReferenceAudios as _asset, index ( _asset.file_id)}
												<div class="flex min-h-32 flex-col items-center justify-center gap-2 rounded-xl border border-border bg-primary/5 p-3 text-center">
													<AudioLines size={34} class="text-primary" />
													<p class="text-xs font-medium">참조 오디오 {index + 1}</p>
												</div>
											{/each}
											{#each referenceAudioFiles as _file, index}
												<div class="flex min-h-32 flex-col items-center justify-center gap-2 rounded-xl border border-border bg-primary/5 p-3 text-center">
													<AudioLines size={34} class="text-primary" />
													<p class="text-xs font-medium">참조 오디오 {selectedReferenceAudios.length + index + 1}</p>
												</div>
											{/each}
										</div>
									{/if}
								</div>

							</div>
						{/if}

						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-width"><span class="text-sm font-medium">가로</span><input id="video-width" type="number" min="32" max="1344" step="32" bind:value={width} class={inputClass} /></label><label class="block space-y-2" for="video-height"><span class="text-sm font-medium">세로</span><input id="video-height" type="number" min="32" max="1344" step="32" bind:value={height} class={inputClass} /></label></div>
						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-duration"><span class="text-sm font-medium">길이(초)</span><input id="video-duration" type="number" min="1" max="15" step="0.1" bind:value={duration} oninput={() => (improvedPrompt = '')} class={inputClass} /></label><label class="block space-y-2" for="video-seed"><span class="text-sm font-medium">Seed</span><input id="video-seed" type="number" min="0" max="9223372036854775807" step="1" bind:value={seed} disabled={randomSeed} required={!randomSeed} class={inputClass} /></label></div>
						<label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition hover:bg-muted" for="random-video-seed"><input id="random-video-seed" type="checkbox" bind:checked={randomSeed} class="size-4 accent-primary" /><span>무작위 시드</span></label>

						<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"><PrimaryButton type="submit" loading={generating} disabled={!prompt.trim() || enhancingPrompt} class="w-full"><Sparkles size={17} strokeWidth={1.9} /><span>{generating ? '생성 중' : '동영상 생성'}</span></PrimaryButton></div>
					</form>
				</section>
			</div>
		</div>
	</Layout>

	<Modal bind:open={selectionOpen} title={selectionTitle} description="기기 저장소 또는 저장된 콘텐츠에서 선택해 주세요.">
		<div class="space-y-5">
			<div class="grid grid-cols-2 gap-2" role="tablist" aria-label="콘텐츠 선택 위치">
				<button type="button" role="tab" aria-selected={selectionSource === 'device'} onclick={() => selectSelectionSource('device')} class={`inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-semibold transition ${selectionSource === 'device' ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'}`}><HardDrive size={16} />기기 저장소</button>
				<button type="button" role="tab" aria-selected={selectionSource === 'stored'} onclick={() => selectSelectionSource('stored')} class={`inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-semibold transition ${selectionSource === 'stored' ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'}`}><Database size={16} />저장된 콘텐츠</button>
			</div>

			{#if selectionSource === 'device'}
				<label class="block space-y-2" for="video-device-file"><span class="text-sm font-medium">파일 선택</span><input id="video-device-file" type="file" accept={selectionKind === 'image' ? 'image/*' : selectionKind === 'video' ? 'video/*' : 'audio/*'} multiple={selectionMultiple} class={fileClass} onchange={handleDeviceSelection} /></label>
			{:else}
				<div class="space-y-4">
					<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
						<SearchBar id="video-stored-search" bind:value={storedSearch} label="저장 콘텐츠 검색" placeholder="파일명으로 검색" oninput={changeStoredFilter} />
						<label class="flex items-center gap-2 text-sm" for="video-stored-sort"><span class="sr-only">정렬</span><select id="video-stored-sort" bind:value={storedSort} onchange={changeStoredFilter} class={inputClass}><option value="latest">최신순</option><option value="oldest">오래된순</option><option value="name">이름순</option></select></label>
					</div>
					{#if storedLoading}
						<div class="flex min-h-48 items-center justify-center"><LoadingSpinner size="md" label="저장 콘텐츠를 불러오는 중" /></div>
					{:else if storedAssets.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">선택할 콘텐츠가 없습니다.</p>
					{:else}
						<div class="grid grid-cols-2 gap-3">
							{#each storedAssets as asset (asset.file_id)}
								<div class={`overflow-hidden rounded-xl border bg-card ${storedSelectedIds.includes(asset.file_id) ? 'border-primary ring-2 ring-primary/20' : 'border-border'}`}>
									<div class="aspect-video bg-muted">
										{#if asset.url && asset.media_kind === 'image'}
											<ImageMedia source={asset.url} sourceType={imageSourceType(asset.url)} alt={storedSourceLabel(asset)} class="h-full" />
										{:else if asset.url && asset.media_kind === 'video'}
											<VideoMedia source={asset.url} sourceType="server" preview={false} muted={true} class="h-full" />
										{:else if asset.media_kind === 'audio'}
											<div class="flex h-full flex-col items-center justify-center gap-2 bg-primary/5"><AudioLines size={34} class="text-primary" /><span class="text-xs font-medium">오디오</span></div>
										{:else}
											<div class="flex h-full items-center justify-center text-xs text-muted-foreground">미리보기 없음</div>
										{/if}
									</div>
									<div class="space-y-2 p-2.5">
										<div class="flex items-center justify-between gap-2 text-[11px] text-muted-foreground"><span>{storedSourceLabel(asset)}</span><span>{new Date(asset.created_at).toLocaleDateString('ko-KR')}</span></div>
										<OutlinedButton class="w-full px-2 text-xs" active={storedSelectedIds.includes(asset.file_id)} onclick={() => toggleStoredAsset(asset)}>{storedSelectedIds.includes(asset.file_id) ? '선택됨' : '선택'}</OutlinedButton>
									</div>
								</div>
							{/each}
						</div>
						{#if storedTotalPages > 1}
							<nav class="flex items-center justify-center gap-4 pt-2" aria-label="저장 콘텐츠 페이지 이동">
								<button type="button" aria-label="이전 저장 콘텐츠 페이지" disabled={storedPage <= 1} onclick={() => changeStoredPage(storedPage - 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft size={18} /></button>
								<span class="text-sm font-medium text-muted-foreground">{storedPage} / {storedTotalPages}</span>
								<button type="button" aria-label="다음 저장 콘텐츠 페이지" disabled={storedPage >= storedTotalPages} onclick={() => changeStoredPage(storedPage + 1)} class="inline-flex size-10 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"><ChevronRight size={18} /></button>
							</nav>
						{/if}
					{/if}
				</div>
			{/if}
		</div>
		{#snippet footer()}
			<OutlinedButton onclick={() => (selectionOpen = false)}>닫기</OutlinedButton>
			{#if selectionSource === 'stored' && selectionMultiple}
				<PrimaryButton disabled={storedSelectedIds.length === 0} onclick={confirmStoredSelection}>선택 완료</PrimaryButton>
			{/if}
		{/snippet}
	</Modal>
	{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="동영상 생성 실패" message={error} onclose={() => (error = '')} /></div>{:else if success}<div class="fixed right-4 top-4 z-50"><Toast state="positive" title="생성 완료" message={success} onclose={() => (success = '')} /></div>{/if}
{/if}
