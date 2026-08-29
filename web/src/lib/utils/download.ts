import { apiBlob } from './api';

function isExternalUrl(source: string) {
	return /^(https?:)?\/\//.test(source);
}

export async function downloadMedia(source: string, filename: string) {
	try {
		const blob = isExternalUrl(source)
			? await fetch(source).then((response) => {
					if (!response.ok) throw new Error('download failed');
					return response.blob();
				})
			: await apiBlob(source);
		const objectUrl = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = objectUrl;
		link.download = filename;
		document.body.appendChild(link);
		link.click();
		link.remove();
		window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
	} catch {
		throw new Error('콘텐츠를 다운로드하지 못했습니다.');
	}
}
