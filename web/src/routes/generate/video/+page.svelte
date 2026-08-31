<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ArrowLeftRight, AudioLines, ChevronLeft, ChevronRight, FolderOpen, HardDrive, Image as ImageIcon, Save, Sparkles, Video, X } from '@lucide/svelte';
	import ImageMedia from '../../../../components/media/image.svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';

	import Modal from '../../../../components/modals/modal.svelte';
	import OutlinedButton from '../../../../components/buttons/outlined-button.svelte';
	import IconOutlinedButton from '../../../../components/buttons/icon-outlined-button.svelte';
	import VideoPresetModal from '../../../../components/presets/video-preset-modal.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import SearchBar from '../../../../components/inputs/searchbar.svelte';
	import Tab from '../../../../components/tabs/tab.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import VideoMedia from '../../../../components/media/video.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { videoGenerationStore, type VideoLibraryAsset, type VideoMode } from '$lib/stores/video-generation.svelte';
	import { apiBlob, apiForm, apiJson } from '$lib/utils/api';
	import { generationJobStore } from '$lib/stores/generation-jobs.svelte';
	import { formatElapsedSeconds } from '$lib/utils/generation';
	import type { Preset, PresetValues } from '$lib/types/presets';

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
	type StoredSource = 'uploaded' | 'generated';
	type VideoPromptLanguage = 'ko' | 'en' | 'ja';
	const modes: { value: VideoMode; label: string; description: string }[] = [
		{ value: 'i2v', label: 'I2V', description: '시작 이미지에서 영상 생성' },
		{ value: 'fl2v', label: 'FL2V', description: '첫·마지막 프레임 사이 생성' },
		{ value: 'r2v', label: 'R2V', description: '참조 이미지·동영상·오디오 기반 생성' }
];
	const modeTabs: { value: VideoMode; label: string }[] = modes.map(({ value, label }) => ({ value, label }));
	const promptLanguageOptions: { value: VideoPromptLanguage; label: string }[] = [
		{ value: 'ko', label: '한글' },
		{ value: 'en', label: '영어' },
		{ value: 'ja', label: '일어' }
	];
	const selectionSourceTabs: { value: SelectionSource; label: string }[] = [
		{ value: 'device', label: '기기 저장소' },
		{ value: 'stored', label: '저장된 콘텐츠' }
	];
	const storedSourceTabs: { value: StoredSource; label: string }[] = [
		{ value: 'uploaded', label: '업로드' },
		{ value: 'generated', label: '생성' }
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
	let fps = $state(24);
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
	let cancelling = $state(false);
	let uploading = $state(false);
	let status = $state('');
	let progress = $state(0);
	let queuePosition = $state<number | null>(null);
	let elapsedSeconds = $state(0);
	let videoUrl = $state('');
	let error = $state('');
	let success = $state('');
	let videoPresetOpen = $state(false);
	let videoPresetLoadOpen = $state(false);
	let videoPresets = $state<Preset[]>([]);
	let videoPresetsLoading = $state(false);
	let videoPresetError = $state('');
	let videoPresetInitialValues = $state<PresetValues>({});
	let active = true;
	let videoJobKey = $state('');
	let announcedTerminal = $state('');
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
	let storedAssetSource = $state<StoredSource>('uploaded');
	let mediaDimensions = $state<Record<string, string>>({});
	let sizeApplying = $state('');
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
		const now = generationJobStore.now;
		const job = videoJobKey ? generationJobStore.jobs[videoJobKey] : undefined;
		if (!job) {
			elapsedSeconds = 0;
			return;
		}
		status = job.status;
		progress = job.progress;
		queuePosition = job.queuePosition;
		elapsedSeconds = generationJobStore.elapsedSeconds(job, now);
		videoUrl = job.videoUrl ?? '';
		const terminalKey = `${videoJobKey}:${job.status}`;
		if (job.status === 'completed' && announcedTerminal !== terminalKey) {
			success = '영상 생성이 완료되었습니다.';
			announcedTerminal = terminalKey;
		}
		if (job.status === 'failed' && announcedTerminal !== terminalKey) {
			error = job.error ?? '영상 생성에 실패했습니다.';
			announcedTerminal = terminalKey;
		}
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
		if (selectedFirst?.url) rememberMediaDimensions('first', selectedFirst.url, 'image');
		if (selectedLast?.url) rememberMediaDimensions('last', selectedLast.url, 'image');
		selectedReferenceImages.forEach((asset) => {
			if (asset.url) rememberMediaDimensions(`reference-image-${asset.file_id}`, asset.url, 'image');
		});
		selectedReferenceVideos.forEach((asset) => {
			if (asset.url) rememberMediaDimensions(`reference-video-${asset.file_id}`, asset.url, 'video');
		});
	}

	function selectMode(next: VideoMode) {
		if (generating) return false;
		if (mode === next) return;
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
		mediaDimensions = {};
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

	function normalizeVideoReferenceMarkers(value: string) {
		return value
			.replace(/\[\s*(?:image|picture)\s*(\d+)\s*\]/gi, '<Picture $1>')
			.replace(/@\s*image\s*(\d+)/gi, '<Picture $1>')
			.replace(/\[\s*video\s*(\d+)\s*\]/gi, '<Video $1>')
			.replace(/@\s*video\s*(\d+)/gi, '<Video $1>')
			.replace(/\[\s*audio\s*(\d+)\s*\]/gi, '<Audio $1>')
			.replace(/@\s*audio\s*(\d+)/gi, '<Audio $1>');
	}

	async function readMediaDimensions(source: Blob | string, kind: 'image' | 'video') {
		let objectUrl = '';
		try {
			if (source instanceof Blob) objectUrl = URL.createObjectURL(source);
			else if (!/^(https?:)?\/\//.test(source)) objectUrl = URL.createObjectURL(await apiBlob(source));
			const url = objectUrl || (typeof source === 'string' ? source : '');
			const element = kind === 'video' ? document.createElement('video') : new Image();
			return await new Promise<{ width: number; height: number }>((resolve, reject) => {
				const succeed = (width: number, height: number) => {
					if (width > 0 && height > 0) resolve({ width, height });
					else reject(new Error('invalid dimensions'));
				};
				element.onerror = () => reject(new Error('media metadata unavailable'));
				if (kind === 'video') {
					const video = element as HTMLVideoElement;
					video.preload = 'metadata';
					video.onloadedmetadata = () => succeed(video.videoWidth, video.videoHeight);
				} else {
					const image = element as HTMLImageElement;
					image.onload = () => succeed(image.naturalWidth, image.naturalHeight);
				}
				element.src = url;
			});
		} finally {
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		}
	}

	async function applyMediaSize(key: string, source: Blob | string | null, kind: 'image' | 'video') {
		if (!source || sizeApplying) return;
		sizeApplying = key;
		error = '';
		try {
			const dimensions = await readMediaDimensions(source, kind);
			width = dimensions.width;
			height = dimensions.height;
			mediaDimensions[key] = `${dimensions.width} × ${dimensions.height}`;
		} catch {
			error = '선택한 콘텐츠의 크기를 읽지 못했습니다.';
		} finally {
			sizeApplying = '';
		}
	}

	function rememberMediaDimensions(key: string, source: Blob | string | null, kind: 'image' | 'video') {
		if (!source) return;
		void readMediaDimensions(source, kind)
			.then(({ width: mediaWidth, height: mediaHeight }) => {
				mediaDimensions[key] = `${mediaWidth} × ${mediaHeight}`;
			})
			.catch(() => {
				mediaDimensions[key] = '크기 확인 실패';
			});
	}

	function mediaDimensionLabel(key: string) {
		return mediaDimensions[key] ?? '크기 확인 중';
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
		storedAssetSource = 'uploaded';
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

	function selectStoredAssetSource(source: StoredSource) {
		if (storedAssetSource === source) return;
		storedAssetSource = source;
		storedPage = 1;
		storedSelectedIds = [];
		storedSelectedAssets = [];
		void loadStoredAssets(1);
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
				source: storedAssetSource,
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
			rememberMediaDimensions('first', files[0], 'image');
		} else if (selectionTarget === 'last') {
			lastFile = files[0];
			selectedLast = null;
			rememberMediaDimensions('last', files[0], 'image');
		} else if (selectionTarget === 'images') {
			referenceImageFiles = [...referenceImageFiles, ...files].slice(0, selectionMax);
			referenceImageFiles.forEach((file, index) => rememberMediaDimensions(`reference-image-file-${index}`, file, 'image'));
		} else if (selectionTarget === 'videos') {
			referenceVideoFiles = [...referenceVideoFiles, ...files].slice(0, selectionMax);
			referenceVideoFiles.forEach((file, index) => rememberMediaDimensions(`reference-video-file-${index}`, file, 'video'));
		} else {
			referenceAudioFiles = [...referenceAudioFiles, ...files].slice(0, selectionMax);
		}
		event.currentTarget.value = '';
		selectionOpen = false;
	}

	function removeMediaDimension(key: string) {
		const next = { ...mediaDimensions };
		delete next[key];
		mediaDimensions = next;
	}

	function removeFirstSelection() {
		firstFile = null;
		selectedFirst = null;
		removeMediaDimension('first');
	}

	function removeLastSelection() {
		lastFile = null;
		selectedLast = null;
		removeMediaDimension('last');
	}

	function removeReferenceImage(index: number) {
		if (index < selectedReferenceImages.length) {
			const asset = selectedReferenceImages[index];
			selectedReferenceImages = selectedReferenceImages.filter((_, currentIndex) => currentIndex !== index);
			removeMediaDimension(`reference-image-${asset.file_id}`);
			return;
		}
		const fileIndex = index - selectedReferenceImages.length;
		referenceImageFiles = referenceImageFiles.filter((_, currentIndex) => currentIndex !== fileIndex);
		referenceImageFiles.forEach((file, currentIndex) => rememberMediaDimensions(`reference-image-file-${currentIndex}`, file, 'image'));
		removeMediaDimension(`reference-image-file-${fileIndex}`);
	}

	function removeReferenceVideo(index: number) {
		if (index < selectedReferenceVideos.length) {
			const asset = selectedReferenceVideos[index];
			selectedReferenceVideos = selectedReferenceVideos.filter((_, currentIndex) => currentIndex !== index);
			removeMediaDimension(`reference-video-${asset.file_id}`);
			return;
		}
		const fileIndex = index - selectedReferenceVideos.length;
		referenceVideoFiles = referenceVideoFiles.filter((_, currentIndex) => currentIndex !== fileIndex);
		referenceVideoFiles.forEach((file, currentIndex) => rememberMediaDimensions(`reference-video-file-${currentIndex}`, file, 'video'));
		removeMediaDimension(`reference-video-file-${fileIndex}`);
	}

	function removeReferenceAudio(index: number) {
		if (index < selectedReferenceAudios.length) {
			selectedReferenceAudios = selectedReferenceAudios.filter((_, currentIndex) => currentIndex !== index);
			return;
		}
		const fileIndex = index - selectedReferenceAudios.length;
		referenceAudioFiles = referenceAudioFiles.filter((_, currentIndex) => currentIndex !== fileIndex);
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
			if (selectedFirst?.url) rememberMediaDimensions('first', selectedFirst.url, 'image');
		} else if (selectionTarget === 'last') {
			selectedLast = assetsToUse[0] ?? null;
			lastFile = null;
			if (selectedLast?.url) rememberMediaDimensions('last', selectedLast.url, 'image');
		} else if (selectionTarget === 'images') {
			selectedReferenceImages = [
				...selectedReferenceImages,
				...assetsToUse.filter((asset) => !selectedReferenceImages.some((item) => item.file_id === asset.file_id))
			].slice(0, selectionMax);
			assetsToUse.forEach((asset) => {
				if (asset.url) rememberMediaDimensions(`reference-image-${asset.file_id}`, asset.url, 'image');
			});
		} else if (selectionTarget === 'videos') {
			selectedReferenceVideos = [
				...selectedReferenceVideos,
				...assetsToUse.filter((asset) => !selectedReferenceVideos.some((item) => item.file_id === asset.file_id))
			].slice(0, selectionMax);
			assetsToUse.forEach((asset) => {
				if (asset.url) rememberMediaDimensions(`reference-video-${asset.file_id}`, asset.url, 'video');
			});
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
			improvedPrompt = normalizeVideoReferenceMarkers(result.improved_prompt.contents);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '프롬프트를 개선하지 못했습니다.';
		} finally {
			enhancingPrompt = false;
		}
	}

	async function generate() {
		videoJobKey = '';
		announcedTerminal = '';
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
				fps: Number(fps),
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
			const accepted = await apiForm<{ prompt_id: string; client_id: string; generation_id: string; created_at: string; elapsed_seconds: number }>(`generation/video/${mode}`, form, { timeout: 120_000 });
			videoJobKey = generationJobStore.track({
				kind: 'video',
				promptId: accepted.prompt_id,
				clientId: accepted.client_id,
				generationId: accepted.generation_id,
				mode,
				createdAt: Date.parse(accepted.created_at),
				elapsedSeconds: accepted.elapsed_seconds
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

	async function cancelGeneration() {
		if (!videoJobKey || !generating || cancelling) return;
		cancelling = true;
		error = '';
		try {
			await generationJobStore.cancel(videoJobKey);
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '영상 생성을 취소하지 못했습니다.';
		} finally {
			cancelling = false;
		}
	}

	function statusLabel(value: string) {
		return { queued: '대기 중', processing: '생성 중', completed: '완료', failed: '실패', cancelled: '취소됨' }[value] ?? value;
	}

	function resetResult() {
		status = '';
		progress = 0;
		queuePosition = null;
		elapsedSeconds = 0;
		videoUrl = '';
		error = '';
		success = '';
		videoJobKey = '';
		announcedTerminal = '';
		generating = false;
		cancelling = false;
	}

	function openVideoPresetSave() {
		videoPresetInitialValues = {
			prompt: prompt.trim(),
			mode,
			width: Number(width),
			height: Number(height),
			duration: Number(duration),
			fps: Number(fps),
			random_seed: randomSeed,
			...(randomSeed || !seed.trim() ? {} : { seed: seed.trim() })
		};
		videoPresetOpen = true;
	}

	async function openVideoPresetLoad() {
		videoPresetLoadOpen = true;
		videoPresetsLoading = true;
		videoPresetError = '';
		try {
			videoPresets = await apiJson<Preset[]>('presets?type=video');
		} catch (reason) {
			videoPresetError = reason instanceof Error ? reason.message : '프리셋을 불러오지 못했습니다.';
			videoPresets = [];
		} finally {
			videoPresetsLoading = false;
		}
	}

	function applyVideoPreset(preset: Preset) {
		const values = preset.values;
		if (values.prompt !== undefined) prompt = values.prompt;
		if (values.mode !== undefined && values.mode !== mode) selectMode(values.mode);
		if (values.width !== undefined) width = values.width;
		if (values.height !== undefined) height = values.height;
		if (values.duration !== undefined) duration = values.duration;
		if (values.fps !== undefined) fps = values.fps;
		if (values.random_seed !== undefined) randomSeed = values.random_seed;
		if (values.seed !== undefined) {
			seed = values.seed;
			randomSeed = false;
		}
		videoPresetLoadOpen = false;
		success = `'${preset.name}' 프리셋을 불러왔습니다.`;
	}

	function videoPresetLabels(preset: Preset) {
		const fields = new Set(preset.saved_fields);
		const labels: Record<string, string> = {
			prompt: '프롬프트',
			mode: '생성 방식',
			size: '영상 크기',
			width: '영상 크기',
			height: '영상 크기',
			duration: '길이',
			fps: 'FPS',
			seed: 'Seed',
			random_seed: 'Seed'
		};
		if (fields.has('width') || fields.has('height')) fields.add('size');
		fields.delete('width');
		fields.delete('height');
		return [...fields].map((field) => labels[field] ?? field).join(', ');
	}
	function handleVideoPresetSaved(preset: Preset) {
		success = `'${preset.name}' 프리셋을 저장했습니다.`;
	}

	function swapDimensions() {
		[width, height] = [height, width];
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
							{#if status}<Typography as="p" variant="muted" class="mt-1">상태: {statusLabel(status)}{#if status === 'queued' || status === 'processing'} · {Math.round(progress)}% · 경과 {formatElapsedSeconds(elapsedSeconds)}{:else} · 소요 {formatElapsedSeconds(elapsedSeconds)}{/if}{#if status === 'queued' && queuePosition !== null} · 대기 {queuePosition}번째{/if}</Typography>{/if}
						</div>
						<Video size={22} class="text-primary" strokeWidth={1.8} />
					</div>
					<div class="mt-6 overflow-hidden rounded-xl border border-border bg-muted/40">
						{#if videoUrl}
							<VideoMedia source={videoUrl} sourceType="server" preview={false} muted={false} class="min-h-[24rem] sm:min-h-[34rem]" />
						{:else if generating}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-4 sm:min-h-[34rem]"><LoadingSpinner size="lg" label={uploading ? '파일 업로드 중' : '영상 생성 중'} /><p class="text-sm text-muted-foreground">{uploading ? '파일을 업로드를 진행하고 있습니다.' : '영상 생성중입니다.'}</p>{#if !uploading}<p class="text-2xl font-semibold tabular-nums text-primary">{Math.round(progress)}%</p>{/if}<p class="text-lg font-semibold tabular-nums text-primary">경과 {formatElapsedSeconds(elapsedSeconds)}</p></div>
					{:else}
							<div class="flex min-h-[24rem] flex-col items-center justify-center gap-3 px-6 text-center sm:min-h-[34rem]"><div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Video size={26} strokeWidth={1.7} /></div><p class="text-sm font-medium">아직 생성된 영상이 없습니다.</p><p class="max-w-sm text-xs leading-5 text-muted-foreground">콘텐츠를 선택하고 프롬프트를 입력한 뒤 생성 버튼을 눌러 주세요.</p></div>
						{/if}
					</div>
					{#if generating && videoJobKey}
						<OutlinedButton class="mt-4 w-full" loading={cancelling} disabled={cancelling} onclick={() => void cancelGeneration()}>
							<X size={16} strokeWidth={1.9} />
							<span>{cancelling ? '영상 생성 취소 중' : '영상 생성 취소'}</span>
						</OutlinedButton>
					{/if}
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="video-settings-title">
					<div class="flex items-center justify-between gap-4">
						<div id="video-settings-title"><Typography as="h2" variant="h2">동영상 설정</Typography></div>
						<div class="flex items-center gap-2">
							<IconOutlinedButton ariaLabel="동영상 프리셋 저장" title="프리셋 저장" disabled={generating} onclick={openVideoPresetSave}>
								<Save size={17} strokeWidth={1.8} />
							</IconOutlinedButton>
							<IconOutlinedButton ariaLabel="동영상 프리셋 불러오기" title="프리셋 불러오기" loading={videoPresetsLoading} disabled={generating} onclick={() => void openVideoPresetLoad()}>
								<FolderOpen size={17} strokeWidth={1.8} />
							</IconOutlinedButton>
						</div>
					</div>
					<Tab items={modeTabs} bind:value={mode} ariaLabel="동영상 생성 방식" onselect={selectMode} class="mt-5" />
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
										<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
											<IconOutlinedButton ariaLabel="시작 이미지 선택 해제" class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={removeFirstSelection}>
												<X size={15} strokeWidth={2} />
											</IconOutlinedButton>
											{#if firstFile}
												<ImageMedia source={firstFile} sourceType="local" alt="선택한 시작 이미지" class="h-full" />
											{:else if selectedFirst?.url}
												<ImageMedia source={selectedFirst.url} sourceType={imageSourceType(selectedFirst.url)} alt="선택한 시작 이미지" class="h-full" />
											{/if}
											<p class="border-t border-border px-3 py-2 text-xs font-medium">시작 이미지 · {mediaDimensionLabel('first')}</p>
											<OutlinedButton class="w-full rounded-none border-0 border-t px-3 text-xs" loading={sizeApplying === 'first'} disabled={Boolean(sizeApplying) && sizeApplying !== 'first'} onclick={() => void applyMediaSize('first', firstFile ?? selectedFirst?.url ?? null, 'image')}>영상 크기로 사용</OutlinedButton>
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
											<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
												<IconOutlinedButton ariaLabel="첫 프레임 선택 해제" class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={removeFirstSelection}>
													<X size={15} strokeWidth={2} />
												</IconOutlinedButton>
												{#if firstFile}
													<ImageMedia source={firstFile} sourceType="local" alt="선택한 첫 프레임" class="h-full" />
												{:else if selectedFirst?.url}
													<ImageMedia source={selectedFirst.url} sourceType={imageSourceType(selectedFirst.url)} alt="선택한 첫 프레임" class="h-full" />
												{/if}
												<p class="border-t border-border px-3 py-2 text-xs font-medium">첫 프레임 · {mediaDimensionLabel('first')}</p>
												<OutlinedButton class="w-full rounded-none border-0 border-t px-3 text-xs" loading={sizeApplying === 'fl2v-first'} disabled={Boolean(sizeApplying) && sizeApplying !== 'fl2v-first'} onclick={() => void applyMediaSize('fl2v-first', firstFile ?? selectedFirst?.url ?? null, 'image')}>영상 크기로 사용</OutlinedButton>
											</div>
										{/if}
									</div>
									<div class="space-y-3">
										<OutlinedButton class="w-full" onclick={() => openSelection('last')}><HardDrive size={16} />마지막 프레임 선택</OutlinedButton>
										{#if lastFile || selectedLast?.url}
											<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
												<IconOutlinedButton ariaLabel="마지막 프레임 선택 해제" class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={removeLastSelection}>
													<X size={15} strokeWidth={2} />
												</IconOutlinedButton>
												{#if lastFile}
													<ImageMedia source={lastFile} sourceType="local" alt="선택한 마지막 프레임" class="h-full" />
												{:else if selectedLast?.url}
													<ImageMedia source={selectedLast.url} sourceType={imageSourceType(selectedLast.url)} alt="선택한 마지막 프레임" class="h-full" />
												{/if}
												<p class="border-t border-border px-3 py-2 text-xs font-medium">마지막 프레임 · {mediaDimensionLabel('last')}</p>
												<OutlinedButton class="w-full rounded-none border-0 border-t px-3 text-xs" loading={sizeApplying === 'fl2v-last'} disabled={Boolean(sizeApplying) && sizeApplying !== 'fl2v-last'} onclick={() => void applyMediaSize('fl2v-last', lastFile ?? selectedLast?.url ?? null, 'image')}>영상 크기로 사용</OutlinedButton>
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
												<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
													<IconOutlinedButton ariaLabel={`참조 이미지 ${index + 1} 선택 해제`} class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={() => removeReferenceImage(index)}>
														<X size={15} strokeWidth={2} />
													</IconOutlinedButton>
													{#if asset.url}
														<ImageMedia source={asset.url} sourceType={imageSourceType(asset.url)} alt={`참조 이미지 ${index + 1}`} class="h-full" />
													{:else}
														<div class="flex min-h-32 items-center justify-center"><ImageIcon size={30} class="text-primary" /></div>
													{/if}
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 이미지 {index + 1} · {mediaDimensionLabel(`reference-image-${asset.file_id}`)}</p>
													<OutlinedButton class="w-full rounded-none border-0 border-t px-3 text-xs" loading={sizeApplying === `reference-image-${asset.file_id}`} disabled={!asset.url || Boolean(sizeApplying) && sizeApplying !== `reference-image-${asset.file_id}`} onclick={() => void applyMediaSize(`reference-image-${asset.file_id}`, asset.url, 'image')}>영상 크기로 사용</OutlinedButton>
												</div>
											{/each}
											{#each referenceImageFiles as file, index}
												<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
													<IconOutlinedButton ariaLabel={`참조 이미지 ${selectedReferenceImages.length + index + 1} 선택 해제`} class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={() => removeReferenceImage(selectedReferenceImages.length + index)}>
														<X size={15} strokeWidth={2} />
													</IconOutlinedButton>
													<ImageMedia source={file} sourceType="local" alt={`참조 이미지 ${selectedReferenceImages.length + index + 1}`} class="h-full" />
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 이미지 {selectedReferenceImages.length + index + 1} · {mediaDimensionLabel(`reference-image-file-${index}`)}</p>
													<OutlinedButton class="w-full rounded-none border-0 border-t px-3 text-xs" loading={sizeApplying === `reference-image-file-${index}`} disabled={Boolean(sizeApplying) && sizeApplying !== `reference-image-file-${index}`} onclick={() => void applyMediaSize(`reference-image-file-${index}`, file, 'image')}>영상 크기로 사용</OutlinedButton>
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
												<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
													<IconOutlinedButton ariaLabel={`참조 동영상 ${index + 1} 선택 해제`} class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={() => removeReferenceVideo(index)}>
														<X size={15} strokeWidth={2} />
													</IconOutlinedButton>
													{#if asset.url}
														<VideoMedia source={asset.url} sourceType="server" preview={false} muted={true} class="h-full" />
													{:else}
														<div class="flex min-h-32 items-center justify-center"><Video size={30} class="text-primary" /></div>
													{/if}
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 동영상 {index + 1} · {mediaDimensionLabel(`reference-video-${asset.file_id}`)}</p>
													<OutlinedButton class="w-full rounded-none border-0 border-t px-3 text-xs" loading={sizeApplying === `reference-video-${asset.file_id}`} disabled={!asset.url || Boolean(sizeApplying) && sizeApplying !== `reference-video-${asset.file_id}`} onclick={() => void applyMediaSize(`reference-video-${asset.file_id}`, asset.url, 'video')}>영상 크기로 사용</OutlinedButton>
												</div>
											{/each}
											{#each referenceVideoFiles as file, index}
												<div class="relative overflow-hidden rounded-xl border border-border bg-muted">
													<IconOutlinedButton ariaLabel={`참조 동영상 ${selectedReferenceVideos.length + index + 1} 선택 해제`} class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={() => removeReferenceVideo(selectedReferenceVideos.length + index)}>
														<X size={15} strokeWidth={2} />
													</IconOutlinedButton>
													<VideoMedia source={file} preview={false} muted={true} class="h-full" />
													<p class="border-t border-border px-3 py-2 text-xs font-medium">참조 동영상 {selectedReferenceVideos.length + index + 1} · {mediaDimensionLabel(`reference-video-file-${index}`)}</p>
													<OutlinedButton class="w-full rounded-none border-0 border-t px-3 text-xs" loading={sizeApplying === `reference-video-file-${index}`} disabled={Boolean(sizeApplying) && sizeApplying !== `reference-video-file-${index}`} onclick={() => void applyMediaSize(`reference-video-file-${index}`, file, 'video')}>영상 크기로 사용</OutlinedButton>
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
												<div class="relative flex min-h-32 flex-col items-center justify-center gap-2 rounded-xl border border-border bg-primary/5 p-3 text-center">
													<IconOutlinedButton ariaLabel={`참조 오디오 ${index + 1} 선택 해제`} class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={() => removeReferenceAudio(index)}>
														<X size={15} strokeWidth={2} />
													</IconOutlinedButton>
													<AudioLines size={34} class="text-primary" />
													<p class="text-xs font-medium">참조 오디오 {index + 1}</p>
												</div>
											{/each}
											{#each referenceAudioFiles as _file, index}
												<div class="relative flex min-h-32 flex-col items-center justify-center gap-2 rounded-xl border border-border bg-primary/5 p-3 text-center">
													<IconOutlinedButton ariaLabel={`참조 오디오 ${selectedReferenceAudios.length + index + 1} 선택 해제`} class="absolute right-2 top-2 z-10 size-8 bg-card/90" onclick={() => removeReferenceAudio(selectedReferenceAudios.length + index)}>
														<X size={15} strokeWidth={2} />
													</IconOutlinedButton>
													<AudioLines size={34} class="text-primary" />
													<p class="text-xs font-medium">참조 오디오 {selectedReferenceAudios.length + index + 1}</p>
												</div>
											{/each}
										</div>
									{/if}
								</div>

							</div>
						{/if}

						<div class="flex items-center justify-between gap-3"><span class="text-sm font-medium">영상 크기</span><IconOutlinedButton ariaLabel="가로와 세로 바꾸기" onclick={swapDimensions}><ArrowLeftRight size={16} strokeWidth={1.9} /></IconOutlinedButton></div>
						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-width"><span class="text-sm font-medium">가로</span><input id="video-width" type="number" min="32" max="1344" step="32" bind:value={width} class={inputClass} /></label><label class="block space-y-2" for="video-height"><span class="text-sm font-medium">세로</span><input id="video-height" type="number" min="32" max="1344" step="32" bind:value={height} class={inputClass} /></label></div>
						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-duration"><span class="text-sm font-medium">길이(초)</span><input id="video-duration" type="number" step="0.1" bind:value={duration} oninput={() => (improvedPrompt = '')} class={inputClass} /></label><label class="block space-y-2" for="video-fps"><span class="text-sm font-medium">FPS</span><input id="video-fps" type="number" min="1" max="120" step="1" bind:value={fps} class={inputClass} /></label></div>
						<div class="grid gap-4 sm:grid-cols-2"><label class="block space-y-2" for="video-seed"><span class="text-sm font-medium">Seed</span><input id="video-seed" type="number" min="0" max="9223372036854775807" step="1" bind:value={seed} disabled={randomSeed} required={!randomSeed} class={inputClass} /></label><label class="flex cursor-pointer items-center gap-3 self-end rounded-lg border border-border px-3 py-2.5 text-sm transition" for="random-video-seed"><input id="random-video-seed" type="checkbox" bind:checked={randomSeed} class="size-4 accent-primary" /><span>무작위 시드</span></label></div>

						<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"><PrimaryButton type="submit" loading={generating} disabled={!prompt.trim() || enhancingPrompt} class="w-full"><Sparkles size={17} strokeWidth={1.9} /><span>{generating ? '생성 중' : '동영상 생성'}</span></PrimaryButton></div>
					</form>
				</section>
			</div>
		</div>
	</Layout>

	<VideoPresetModal bind:open={videoPresetOpen} preset={null} initialValues={videoPresetInitialValues} onSaved={handleVideoPresetSaved} />

	<Modal bind:open={videoPresetLoadOpen} title="VIDEO GEN 프리셋 불러오기" description="저장된 동영상 설정을 선택해 적용합니다." closeOnBackdrop={!videoPresetsLoading}>
		{#if videoPresetsLoading}
			<div class="flex justify-center py-8"><LoadingSpinner size="md" label="VIDEO GEN 프리셋 불러오는 중" /></div>
		{:else if videoPresetError}
			<p class="py-4 text-sm text-destructive" role="alert">{videoPresetError}</p>
		{:else if videoPresets.length === 0}
			<p class="py-4 text-sm text-muted-foreground">저장된 VIDEO GEN 프리셋이 없습니다.</p>
		{:else}
			<div class="space-y-2">
				{#each videoPresets as preset (preset.id)}
					<div class="flex items-center justify-between gap-4 rounded-xl border border-border p-3">
						<div class="min-w-0">
							<p class="truncate text-sm font-semibold">{preset.name}</p>
							<p class="mt-1 truncate text-xs text-muted-foreground">{videoPresetLabels(preset)}</p>
						</div>
						<OutlinedButton class="shrink-0 px-3 text-xs" onclick={() => applyVideoPreset(preset)}>불러오기</OutlinedButton>
					</div>
				{/each}
			</div>
		{/if}
	</Modal>

	<Modal bind:open={selectionOpen} title={selectionTitle} description="기기 저장소 또는 저장된 콘텐츠에서 선택해 주세요.">
		<div class="space-y-5">
			<Tab items={selectionSourceTabs} bind:value={selectionSource} ariaLabel="콘텐츠 선택 위치" onselect={selectSelectionSource} />

			{#if selectionSource === 'device'}
				<label class="block space-y-2" for="video-device-file"><span class="text-sm font-medium">파일 선택</span><input id="video-device-file" type="file" accept={selectionKind === 'image' ? 'image/*' : selectionKind === 'video' ? 'video/*' : 'audio/*'} multiple={selectionMultiple} class={fileClass} onchange={handleDeviceSelection} /></label>
			{:else}
				<div class="space-y-4">
					<Tab items={storedSourceTabs} bind:value={storedAssetSource} ariaLabel="저장된 콘텐츠 종류" onselect={selectStoredAssetSource} />
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
