import type { MossSettings } from './moss';

export type ImageGenerationMode = 't2i' | 'i2i';
export type ImageModelFamily = 'anima' | 'krea2' | 'moss' | 'minimax_h3_image';
export type ImagePresetType = 't2i_anima' | 'i2i_anima' | 't2i_krea2' | 'i2i_krea2' | 't2i_moss' | 't2i_minimax_h3_image' | 'i2i_minimax_h3_image';
export const imageModelFamilyTabs: { value: ImageModelFamily; label: string }[] = [
	{ value: 'anima', label: 'ANIMA' },
	{ value: 'moss', label: 'MOSS' },
	{ value: 'minimax_h3_image', label: 'MINIMAX H3 IMAGE' },
];
export const imageGenerationFamilyTabs = imageModelFamilyTabs;
export const imageModelFamilyLabels: Record<ImageModelFamily, string> = { anima: 'Anima', krea2: 'Krea2', moss: 'MOSS', minimax_h3_image: 'MiniMax H3-Image' };
export const imageGenerationModeTabs: { value: ImageGenerationMode; label: string }[] = [
	{ value: 't2i', label: 'T2I' },
	{ value: 'i2i', label: 'I2I' }
];
export const imagePresetCategories: { value: ImagePresetType; label: string; generationMode: ImageGenerationMode; modelFamily: ImageModelFamily }[] = [
	{ value: 't2i_anima', label: 'T2I (Anima)', generationMode: 't2i', modelFamily: 'anima' },
	{ value: 'i2i_anima', label: 'I2I (Anima)', generationMode: 'i2i', modelFamily: 'anima' },
	{ value: 't2i_moss', label: 'T2I (MOSS)', generationMode: 't2i', modelFamily: 'moss' },
	{ value: 't2i_minimax_h3_image', label: 'T2I (MiniMax H3-Image)', generationMode: 't2i', modelFamily: 'minimax_h3_image' },
	{ value: 'i2i_minimax_h3_image', label: 'I2I (MiniMax H3-Image)', generationMode: 'i2i', modelFamily: 'minimax_h3_image' },
	{ value: 't2i_krea2', label: 'T2I (Krea2)', generationMode: 't2i', modelFamily: 'krea2' },
	{ value: 'i2i_krea2', label: 'I2I (Krea2)', generationMode: 'i2i', modelFamily: 'krea2' },
];
export type PresetType = ImagePresetType | 'video';
export type VideoMode = 'i2v' | 'fl2v' | 'r2v';
export type VideoUpscaleMode = 'learned_3d';
export type AspectRatio = 'custom' | '2:3' | '3:2' | '1:1' | '16:9' | '9:16';
export type LoraSelection = { name: string; strength: number };

export type PresetValues = {
	moss?: MossSettings;
	positive_prompt_prefix?: string;
	prompt?: string;
	negative_prompt_prefix?: string;
	negative_prompt?: string;
	prompt_enhancement_enabled?: boolean;
	improved_prompt?: string;
	checkpoint?: string;
	loras?: LoraSelection[];
	aspect_ratio?: AspectRatio;
	megapixels?: number;
	upscale_mode?: VideoUpscaleMode;
	target_megapixels?: number;
	width?: number;
	height?: number;
	denoise?: number;
	cfg?: number;
	steps?: number;
	use_pdd?: boolean;
	sampler_name?: string;
	scheduler?: string;
	mode?: VideoMode;
	duration?: number;
	fps?: number;
	seed?: string;
	random_seed?: boolean;
};

export type Preset = {
	id: string;
	type: PresetType;
	name: string;
	values: PresetValues;
	is_default: boolean;
	saved_fields: string[];
	created_at: string;
	updated_at: string;
};

export type ImageOptions = {
	prompt_enhancer_available?: boolean;
	checkpoints: string[];
	loras: string[];
	samplers: string[];
	schedulers: string[];
	default_checkpoint: string;
	default_sampler: string;
	default_scheduler: string;
	default_cfg?: number;
	default_steps?: number;
};

export type VideoGenerationOptions = {
	mode: VideoMode;
	checkpoints: string[];
	default_checkpoint: string;
	loras: string[];
	samplers: string[];
	schedulers: string[];
	default_sampler: string;
	default_scheduler: string;
	pdd_available: boolean;
	learned_upscale_available: boolean;
};
