export type MossLayoutElement = {
	kind: 'object' | 'character' | 'text';
	caption: string;
	text: string;
	x: number;
	y: number;
	width: number;
	height: number;
};

export type MossSettings = {
	layout_enabled: boolean;
	elements: MossLayoutElement[];
};

export function mossSettings(value?: Partial<MossSettings> | null): MossSettings {
	return { layout_enabled: value?.layout_enabled ?? false, elements: (value?.elements ?? []).map((element) => ({ ...element })) };
}
