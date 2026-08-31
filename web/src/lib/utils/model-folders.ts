export function modelFolders(values: string[]) {
	return [...new Set(values.flatMap((value) => {
		const segments = value.split('/');
		return segments.slice(0, -1).map((_, index) => segments.slice(0, index + 1).join('/'));
	}))].sort((a, b) => a.localeCompare(b));
}

export function filterModelFolder(values: string[], folder: string) {
	return folder ? values.filter((value) => value.startsWith(`${folder}/`)) : values;
}

export function parentModelFolder(folder: string) {
	return folder.includes('/') ? folder.slice(0, folder.lastIndexOf('/')) : '';
}
