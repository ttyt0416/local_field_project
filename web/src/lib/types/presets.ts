export type PresetType = 't2i' | 'video';
export type VideoMode = 'i2v' | 'fl2v' | 'r2v';
export type AspectRatio = 'custom' | '2:3' | '3:2' | '1:1' | '16:9' | '9:16';
export type LoraSelection = { name: string; strength: number };

export type PresetValues = {
	prompt?: string;
	negative_prompt?: string;
	prompt_enhancement_enabled?: boolean;
	improved_prompt?: string;
	checkpoint?: string;
	loras?: LoraSelection[];
	aspect_ratio?: AspectRatio;
	width?: number;
	height?: number;
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
