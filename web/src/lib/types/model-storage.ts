export const modelTypes = [
	{ value: 'checkpoint', label: '체크포인트', directory: 'checkpoints' },
	{ value: 'diffusion_model', label: 'Diffusion Model', directory: 'diffusion_models' },
	{ value: 'lora', label: 'LoRA', directory: 'loras' },
	{ value: 'text_encoder', label: '텍스트 인코더', directory: 'text_encoders' },
	{ value: 'vae', label: 'VAE', directory: 'vae' },
	{ value: 'embedding', label: '임베딩', directory: 'embeddings' }
] as const;

export type ModelType = (typeof modelTypes)[number]['value'];
export type InstalledModel = {
	model_type: ModelType;
	filename: string;
	size_bytes: number;
	modified_at: string;
};
export type ModelFolder = { model_type: ModelType; subfolder: string };

export function modelTypeInfo(value: ModelType) {
	return modelTypes.find((item) => item.value === value)!;
}
