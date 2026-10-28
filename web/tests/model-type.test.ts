import { inferModelType } from '../src/lib/utils/model-type.ts';

const cases = [
	['split_files/diffusion_models/model.safetensors', 'owner/repo', 'diffusion_model'],
	['checkpoints/model.safetensors', 'owner/Flux', 'checkpoint'],
	['unet/model.gguf', 'owner/repo', 'diffusion_model'],
	['transformer/diffusion_pytorch_model.safetensors', 'owner/repo', 'diffusion_model'],
	['text_encoder_2/model.safetensors', 'owner/Qwen-Image', 'text_encoder'],
	['split_files/vae/model.safetensors', 'owner/MOSS', 'vae'],
	['loras/style.safetensors', 'owner/Anima', 'lora'],
	['embeddings/style.pt', 'owner/Illustrious', 'embedding'],
	['t5xxl_fp8.safetensors', 'owner/Flux', 'text_encoder'],
	['clip_l.safetensors', 'owner/SDXL', 'text_encoder'],
	['model_vae.safetensors', 'owner/Anima', 'vae'],
	['flux_lora.safetensors', 'owner/Flux', 'lora'],
	['model.safetensors', 'owner/MOSS-Image', 'diffusion_model'],
	['model.gguf', 'owner/Wan2.2', 'diffusion_model'],
	['model.safetensors', 'owner/Qwen-Image-2.1', 'diffusion_model'],
	['model.safetensors', 'owner/Illustrious', 'checkpoint'],
	['model.safetensors', 'owner/repo', null]
] as const;

for (const [path, repo, expected] of cases) {
	const actual = inferModelType(path, repo);
	if (actual !== expected) throw new Error(`${repo}/${path}: expected ${expected}, received ${actual}`);
}
console.log(`Model type inference: ${cases.length} cases passed`);
