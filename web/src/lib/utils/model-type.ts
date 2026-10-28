import { modelTypes, type ModelType } from '../types/model-storage.ts';

export function inferModelType(path: string, repoId = ''): ModelType | null {
	const segments = path.toLowerCase().split('/');
	for (const segment of segments.slice(0, -1).reverse()) {
		const normalized = segment.replace(/[\s_-]+/g, '');
		const type = modelTypes.find((item) => item.directory.replace(/_/g, '') === normalized);
		if (type) return type.value;
		if (['unet', 'transformer'].includes(normalized)) return 'diffusion_model';
		if (/^textencoder\d*$/.test(normalized)) return 'text_encoder';
	}
	return inferName(segments.at(-1) ?? '') ?? inferName(repoId.split('/').at(-1) ?? '');
}

function inferName(value: string): ModelType | null {
	const name = value.toLowerCase().replace(/[^a-z0-9]+/g, '_');
	if (/(^|_)(lora|loras|locon|dora)(_|$)/.test(name)) return 'lora';
	if (/(^|_)(vae|ae)(_|$)/.test(name)) return 'vae';
	if (/(^|_)(text_?encoders?\d*|t5\w*|umt5\w*|clip_[lg]|qwen\d*\w*vl)(_|$)/.test(name)) return 'text_encoder';
	if (/(^|_)(embeddings?|textual_?inversion)(_|$)/.test(name)) return 'embedding';
	if (/(^|_)(checkpoints?|illustrious|sdxl|sd_?1_?5)(_|$)/.test(name)) return 'checkpoint';
	if (/(^|_)(diffusion_?models?|unet|transformer|anima|flux\w*|wan\d*|hunyuan\w*|qwen_?image|moss|minimax)(_|$)/.test(name)) return 'diffusion_model';
	return null;
}
