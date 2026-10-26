import { apiBlob } from './api';
import { reportApiError, startApiTiming } from './telemetry';

function isExternalUrl(source: string) {
	return /^(https?:)?\/\//.test(source);
}

export async function downloadMedia(source: string, filename: string) {
	const timing = isExternalUrl(source) ? startApiTiming(source, 'GET') : null;
	try {
		const blob = isExternalUrl(source)
			? await fetch(source).then((response) => {
					timing?.headers(response.status);
					if (!response.ok) throw Object.assign(new Error(`HTTP ${response.status}: ${response.statusText}`), { response });
					return response.blob();
				})
			: await apiBlob(source);
		timing?.finish();
		const objectUrl = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = objectUrl;
		link.download = filename;
		document.body.appendChild(link);
		link.click();
		link.remove();
		window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
	} catch (error) {
		timing?.fail(error);
		if (isExternalUrl(source)) reportApiError(error, source, 'GET');
		throw new Error('콘텐츠를 다운로드하지 못했습니다.', { cause: error });
	}
}
