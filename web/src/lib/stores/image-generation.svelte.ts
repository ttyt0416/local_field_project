export type ImageGenerationParameters = {
	prompt: string;
	negative_prompt: string;
	checkpoint: string;
	loras: { name: string; strength: number }[];
	cfg: number;
	steps: number;
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
