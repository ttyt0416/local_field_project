export type ImageGenerationParameters = {
	model_family?: 'anima' | 'illustrious';
	generation_mode?: 't2i' | 'i2i';
	source_file_id?: string | null;
	source_image_url?: string | null;
	denoise?: number;
	prompt: string;
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
