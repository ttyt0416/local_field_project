export type VideoMode = 'i2v' | 'fl2v' | 'r2v';
export type VideoLibraryAsset = {
	file_id: string;
	filename: string;
	content_type: string;
	media_kind: 'image' | 'audio' | 'video';
	url: string | null;
};

type PendingVideoSelection = {
	mode: VideoMode;
	firstFrame?: VideoLibraryAsset;
	lastFrame?: VideoLibraryAsset;
	referenceImages: VideoLibraryAsset[];
	referenceAudios: VideoLibraryAsset[];
};

let pending: PendingVideoSelection | null = null;

function ensure(mode: VideoMode) {
	if (!pending || pending.mode !== mode) {
		pending = { mode, referenceImages: [], referenceAudios: [] };
	}
	return pending;
}

export const videoGenerationStore = {
	setFirstFrame(asset: VideoLibraryAsset, mode: VideoMode = 'i2v') {
	  ensure(mode).firstFrame = asset;
	},
	setLastFrame(asset: VideoLibraryAsset) {
		ensure('fl2v').lastFrame = asset;
	},
	addReferenceImage(asset: VideoLibraryAsset) {
		const state = ensure('r2v');
		if (!state.referenceImages.some((item) => item.file_id === asset.file_id)) state.referenceImages.push(asset);
	},
	addReferenceAudio(asset: VideoLibraryAsset) {
		const state = ensure('r2v');
		if (!state.referenceAudios.some((item) => item.file_id === asset.file_id)) state.referenceAudios.push(asset);
	},
	consume(): PendingVideoSelection | null {
	  if (!pending) return null;
		const value = pending;
		pending = null;
		return value;
	}
};
