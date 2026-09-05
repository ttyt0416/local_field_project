export type ImageGenerationMode = 't2i' | 'i2i';
export type ImageModelFamily = 'anima' | 'illustrious' | 'krea2';
export type ImagePresetType = 't2i_anima' | 'i2i_anima' | 't2i_illustrious' | 'i2i_illustrious' | 't2i_krea2' | 'i2i_krea2';
export const imageModelFamilyTabs: { value: ImageModelFamily; label: string }[] = [
	{ value: 'anima', label: 'ANIMA' },
	{ value: 'illustrious', label: 'ILLUSTRIOUS' },
	{ value: 'krea2', label: 'KREA2' }
];
export const imageGenerationModeTabs: { value: ImageGenerationMode; label: string }[] = [
	{ value: 't2i', label: 'T2I' },
	{ value: 'i2i', label: 'I2I' }
];
export const imagePresetCategories: { value: ImagePresetType; label: string; generationMode: ImageGenerationMode; modelFamily: ImageModelFamily }[] = [
	{ value: 't2i_anima', label: 'T2I (Anima)', generationMode: 't2i', modelFamily: 'anima' },
	{ value: 'i2i_anima', label: 'I2I (Anima)', generationMode: 'i2i', modelFamily: 'anima' },
	{ value: 't2i_illustrious', label: 'T2I (Illustrious)', generationMode: 't2i', modelFamily: 'illustrious' },
	{ value: 'i2i_illustrious', label: 'I2I (Illustrious)', generationMode: 'i2i', modelFamily: 'illustrious' },
	{ value: 't2i_krea2', label: 'T2I (Krea2)', generationMode: 't2i', modelFamily: 'krea2' },
	{ value: 'i2i_krea2', label: 'I2I (Krea2)', generationMode: 'i2i', modelFamily: 'krea2' }
];
export type PresetType = ImagePresetType | 'video';
export type VideoMode = 'i2v' | 'fl2v' | 'r2v';
export type AspectRatio = 'custom' | '2:3' | '3:2' | '1:1' | '16:9' | '9:16';
export type LoraSelection = { name: string; strength: number };

export type PresetValues = {
	positive_prompt_prefix?: string;
	prompt?: string;
	negative_prompt_prefix?: string;
	negative_prompt?: string;
	prompt_enhancement_enabled?: boolean;
	improved_prompt?: string;
	checkpoint?: string;
	loras?: LoraSelection[];
	aspect_ratio?: AspectRatio;
	width?: number;
	height?: number;
	denoise?: number;
	cfg?: number;
	steps?: number;
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
	checkpoints: string[];
	loras: string[];
	samplers: string[];
	schedulers: string[];
	default_checkpoint: string;
	default_sampler: string;
	default_scheduler: string;
};

export type VideoGenerationOptions = {
	mode: VideoMode;
	checkpoints: string[];
	default_checkpoint: string;
};
