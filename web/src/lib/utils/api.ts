import ky, { HTTPError, isTimeoutError, type Options, type ResponsePromise } from 'ky';
import { SERVER_URL } from '$lib/configs/constants';

export { trackWebEvent } from './telemetry';
export type { WebEvent } from './telemetry';
import { reportApiError, startApiTiming } from './telemetry';

const api = ky.create({
	baseUrl: `${SERVER_URL.replace(/\/+$/, '')}/`,
	retry: 0,
	timeout: 15_000
});

function getErrorMessage(error: unknown) {
	if (error instanceof HTTPError) {
		const body = error.data;
		if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string' && body.detail.trim()) return body.detail;
		switch (error.response.status) {
			case 400:
				return '요청 내용을 확인해 주세요.';
			case 401:
				return '요청을 처리할 권한이 없습니다.';
			case 403:
				return '이 작업을 수행할 권한이 없습니다.';
			case 404:
				return '요청한 정보를 찾을 수 없습니다.';
			case 409:
				return '이미 존재하거나 현재 상태와 충돌하는 요청입니다.';
			case 413:
				return '전송할 파일의 크기가 너무 큽니다.';
			case 415:
				return '지원하지 않는 형식입니다.';
			case 422:
				return '입력값을 확인해 주세요.';
			case 429:
				return '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
			default:
				return error.response.status >= 500
					? '서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.'
					: '요청을 처리하지 못했습니다.';
		}
	}
	if (isTimeoutError(error)) return '요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.';
	if (error instanceof Error && error.name === 'AbortError') return '요청이 취소되었습니다.';
	return '서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.';
}

function timedOptions(options: Options | undefined, timing: ReturnType<typeof startApiTiming>): Options {
	return {
		...options,
		hooks: {
			...options?.hooks,
			afterResponse: [({ response }) => timing.headers(response.status), ...(options?.hooks?.afterResponse ?? [])]
		}
	};
}

async function timedRequest<T>(path: string, options: Options | undefined, read: (response: ResponsePromise) => Promise<T>): Promise<T> {
	const method = options?.method ?? 'GET';
	const timing = startApiTiming(path, method);
	try {
		const response = api(path, timedOptions(options, timing));
		return await read(response);
	} catch (error) {
		timing.fail(error);
		reportApiError(error, path, method);
		throw new Error(getErrorMessage(error), { cause: error });
	} finally {
		timing.finish();
	}
}

export function apiJson<T>(path: string, options?: Options) {
	return timedRequest<T>(path, options, (response) => response.json<T>());
}

export function apiForm<T>(path: string, form: FormData, options?: Options) {
	return timedRequest<T>(path, { ...options, method: options?.method ?? 'POST', body: form }, (response) => response.json<T>());
}

export function apiBlob(path: string, options?: Options) {
	return timedRequest(path, options, (response) => response.blob());
}

export async function apiDelete(path: string) {
	await timedRequest(path, { method: 'DELETE' }, async (response) => { await response; });
}

export type ServerSentEvent = {
	event: string;
	data: string;
};

type StreamSseOptions = {
	signal?: AbortSignal;
	onConnected?: () => void;
};

export async function streamSse(
	path: string,
	onEvent: (event: ServerSentEvent) => void,
	options?: StreamSseOptions
) {
	const timing = startApiTiming(path, 'GET', true);
	try {
		const response = await api(path, timedOptions({
			timeout: false,
			signal: options?.signal,
			headers: { Accept: 'text/event-stream' }
		}, timing));
		if (!response.body) throw new Error('SSE 응답 스트림을 사용할 수 없습니다.');
		options?.onConnected?.();

		const reader = response.body.getReader();
		const decoder = new TextDecoder();
		let buffer = '';

		const dispatch = (block: string) => {
			let event = 'message';
			const data: string[] = [];
			for (const rawLine of block.split('\n')) {
				const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine;
				if (line.startsWith('event:')) event = line.slice(6).trim();
				if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
			}
			if (data.length) onEvent({ event, data: data.join('\n') });
		};

		while (true) {
			const { done, value } = await reader.read();
			if (value?.length) timing.firstByte();
			buffer += decoder.decode(value, { stream: !done });
			let separator = buffer.indexOf('\n\n');
			while (separator >= 0) {
				dispatch(buffer.slice(0, separator));
				buffer = buffer.slice(separator + 2);
				separator = buffer.indexOf('\n\n');
			}
			if (done) {
				if (buffer.trim()) dispatch(buffer);
				return;
			}
		}
	} catch (error) {
		timing.fail(error);
		reportApiError(error, path, 'GET');
		throw new Error(getErrorMessage(error), { cause: error });
	} finally {
		timing.finish();
	}
}
