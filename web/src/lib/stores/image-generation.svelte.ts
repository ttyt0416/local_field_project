import type { MossSettings } from '$lib/types/moss';

export type ImageGenerationParameters = {
	model_family?: 'anima' | 'krea2' | 'moss';
	moss?: Partial<MossSettings>;
	prompt_enhancement_enabled?: boolean;
	improved_prompt?: string;
	generation_mode?: 't2i' | 'i2i';
	source_file_id?: string | null;
	source_image_url?: string | null;
	reference_images?: { file_id: string; filename: string; url: string | null }[];
	denoise?: number;
	positive_prompt_prefix?: string;
	prompt: string;
	negative_prompt_prefix?: string;
	negative_prompt: string;
	checkpoint: string;
	loras: { name: string; strength: number }[];
	cfg: number;
	steps: number;
	sampler_name: string;
	scheduler: string;
	width: number;
	height: number;
	seed: string;
};

class ImageGenerationStore {
	pending = $state<ImageGenerationParameters | null>(null);

	set(parameters: ImageGenerationParameters) {
		this.pending = parameters;
	}

	consume() {
		const parameters = this.pending;
		this.pending = null;
		return parameters;
	}
}

export const imageGenerationStore = new ImageGenerationStore();
