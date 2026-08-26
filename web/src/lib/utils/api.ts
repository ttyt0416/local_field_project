import { browser } from '$app/environment';
import ky, { HTTPError, isTimeoutError, type Options } from 'ky';
import { SERVER_URL } from '$lib/configs/constants';

export const ACCESS_TOKEN_KEY = 'local-field.access-token';

export type WebEvent = {
	event_type: 'click' | 'route';
	page_path: string;
	from_path?: string | null;
	target_type: string;
	target_id?: string | null;
	target_label?: string | null;
	target_href?: string | null;
};

const api = ky.create({
	baseUrl: `${SERVER_URL.replace(/\/+$/, '')}/`,
	retry: 0,
	timeout: 15_000,
	hooks: {
		beforeRequest: [
			({ request }) => {
				if (!browser || request.headers.has('Authorization')) return;
				const token = localStorage.getItem(ACCESS_TOKEN_KEY);
				if (token) {
					request.headers.set('Authorization', `Bearer ${token}`);
				}
			}
		]
	}
});

function getErrorMessage(error: unknown) {
	if (error instanceof HTTPError) {
		switch (error.response.status) {
			case 400:
				return '요청 내용을 확인해 주세요.';
			case 401:
				return '인증 정보가 올바르지 않거나 로그인이 만료되었습니다.';
			case 403:
				return '이 작업을 수행할 권한이 없습니다.';
			case 404:
				return '요청한 정보를 찾을 수 없습니다.';
			case 409:
				return '이미 존재하는 정보와 충돌했습니다.';
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

export async function apiJson<T>(path: string, options?: Options) {
	try {
		return await api(path, options).json<T>();
	} catch (error) {
		throw new Error(getErrorMessage(error));
	}
}

export async function apiBlob(path: string, options?: Options) {
	try {
		return await api(path, options).blob();
	} catch (error) {
		throw new Error(getErrorMessage(error));
	}
}

export async function trackWebEvent(event: WebEvent) {
	try {
		await api('web/events', { method: 'POST', json: event, timeout: 5_000, keepalive: true });
	} catch {
		// Telemetry must not block the interaction it records.
	}
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
	try {
		const response = await api(path, {
			timeout: false,
			signal: options?.signal,
			headers: { Accept: 'text/event-stream' }
		});
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
		throw new Error(getErrorMessage(error));
	}
}
