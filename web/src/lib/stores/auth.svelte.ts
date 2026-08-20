import { browser } from '$app/environment';
import { SERVER_URL } from '$lib/configs/constants';

export type AuthUser = {
	id: string;
	email: string;
};

type AuthResponse = {
	access_token: string;
	token_type: string;
	user: AuthUser;
};

const ACCESS_TOKEN_KEY = 'local-field.access-token';

class AuthStore {
	token = $state<string | null>(null);
	user = $state<AuthUser | null>(null);
	initialized = $state(false);
	private initialization?: Promise<void>;

	get isAuthenticated() {
		return Boolean(this.token && this.user);
	}

	async initialize() {
		if (this.initialization) {
			return this.initialization;
		}

		this.initialization = this.restoreSession();
		return this.initialization;
	}

	async login(email: string, password: string) {
		const session = await this.authenticate('/auth/login', { email, password });
		this.setSession(session);
	}

	async signup(email: string, password: string) {
		const session = await this.authenticate('/auth/signup', { email, password });
		this.setSession(session);
	}

	clearSession() {
		this.token = null;
		this.user = null;
		if (browser) {
			localStorage.removeItem(ACCESS_TOKEN_KEY);
		}
	}

	private async restoreSession() {
		if (!browser) {
			this.initialized = true;
			return;
		}

		const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
		if (!storedToken) {
			this.initialized = true;
			return;
		}

		this.token = storedToken;
		try {
			const response = await fetch(`${SERVER_URL}/auth/me`, {
			headers: { Authorization: `Bearer ${storedToken}` }
			});
			if (!response.ok) {
				throw new Error('인증 세션이 만료되었습니다.');
			}
			this.user = (await response.json()) as AuthUser;
		} catch {
			this.clearSession();
		} finally {
			this.initialized = true;
		}
	}

	private async authenticate(path: string, credentials: { email: string; password: string }) {
		const response = await fetch(`${SERVER_URL}${path}`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(credentials)
		});
		const payload = (await response.json().catch(() => ({}))) as {
			detail?: string;
		};
		if (!response.ok) {
			throw new Error(payload.detail || '인증 요청에 실패했습니다.');
		}
		return payload as AuthResponse;
	}

	private setSession(session: AuthResponse) {
		this.token = session.access_token;
		this.user = session.user;
		this.initialized = true;
		if (browser) {
			localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
		}
	}
}

export const authStore = new AuthStore();
