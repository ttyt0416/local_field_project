import { browser } from '$app/environment';
import ky, { HTTPError, type Options } from 'ky';
import { SERVER_URL } from '$lib/configs/constants';

export const ACCESS_TOKEN_KEY = 'local-field.access-token';

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
