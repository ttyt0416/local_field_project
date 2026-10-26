export type VideoPromptSource = { filename: string; file?: Blob; fileId?: string };
export type VideoPromptReference = {
	kind: 'image' | 'video' | 'audio';
	index: number;
	role: 'first_frame' | 'last_frame' | 'identity' | 'motion' | 'audio' | 'continuation_frame';
	filename: string;
	image_data_url?: string;
};

type ReferenceSelection = {
	mode: 'i2v' | 'fl2v' | 'r2v';
	continuationMode: 'i2v' | 'r2v';
	segmentIndex: number;
	first: VideoPromptSource | null;
	last: VideoPromptSource | null;
	images: VideoPromptSource[];
	videos: VideoPromptSource[];
	audios: VideoPromptSource[];
};

export async function buildVideoPromptReferences(selection: ReferenceSelection, preview: (source: VideoPromptSource) => Promise<string>): Promise<VideoPromptReference[]> {
	const references: VideoPromptReference[] = [];
	async function image(source: VideoPromptSource | null, index: number, role: VideoPromptReference['role']) {
		if (source) references.push({ kind: 'image', index, role, filename: source.filename.slice(0, 255), image_data_url: await preview(source) });
	}
	if (selection.segmentIndex > 0) {
		references.push({ kind: 'image', index: 1, role: 'continuation_frame', filename: '' });
		if (selection.continuationMode === 'r2v') {
			for (const [index, source] of selection.images.entries()) await image(source, index + 2, 'identity');
		}
	} else if (selection.mode === 'r2v') {
		for (const [index, source] of selection.images.entries()) await image(source, index + 1, 'identity');
		for (const [index, source] of selection.videos.entries()) references.push({ kind: 'video', index: index + 1, role: 'motion', filename: source.filename.slice(0, 255) });
		for (const [index, source] of selection.audios.entries()) references.push({ kind: 'audio', index: index + 1, role: 'audio', filename: source.filename.slice(0, 255) });
	} else {
		await image(selection.first, 1, 'first_frame');
		if (selection.mode === 'fl2v') await image(selection.last, 2, 'last_frame');
	}
	return references;
}

export async function createVideoPromptPreview(source: Blob): Promise<string> {
	const image = await createImageBitmap(source);
	try {
		const scale = Math.min(1, 768 / Math.max(image.width, image.height));
		const canvas = document.createElement('canvas');
		canvas.width = Math.max(1, Math.round(image.width * scale));
		canvas.height = Math.max(1, Math.round(image.height * scale));
		const context = canvas.getContext('2d');
		if (!context) throw new Error('참조 이미지 미리보기를 만들 수 없습니다.');
		context.fillStyle = '#fff';
		context.fillRect(0, 0, canvas.width, canvas.height);
		context.drawImage(image, 0, 0, canvas.width, canvas.height);
		return canvas.toDataURL('image/jpeg', 0.85);
	} finally {
		image.close();
	}
}
