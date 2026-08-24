import { browser } from '$app/environment';
import ky, { HTTPError, type Options } from 'ky';
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

function getErrorMessage(error: HTTPError) {
	if (typeof error.data === 'object' && error.data !== null && 'detail' in error.data) {
		const detail = error.data.detail;
		if (typeof detail === 'string') return detail;
	}
	return `API 요청에 실패했습니다. (${error.response.status})`;
}

export async function apiJson<T>(path: string, options?: Options) {
	try {
		return await api(path, options).json<T>();
	} catch (error) {
		if (error instanceof HTTPError) {
			throw new Error(getErrorMessage(error));
		}
		throw error;
	}
}

export async function apiBlob(path: string, options?: Options) {
	try {
		return await api(path, options).blob();
	} catch (error) {
		if (error instanceof HTTPError) {
			throw new Error(getErrorMessage(error));
		}
		throw error;
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
		if (error instanceof HTTPError) throw new Error(getErrorMessage(error));
		throw error;
	}
}
