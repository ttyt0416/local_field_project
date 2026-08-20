import { browser } from '$app/environment';
import { ACCESS_TOKEN_KEY, apiJson } from '$lib/utils/api';
import { isJwtUsable } from '$lib/utils/jwt';

export type AuthUser = {
	id: string;
	email: string;
};

type AuthResponse = {
	access_token: string;
	token_type: string;
	user: AuthUser;
};

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
		if (!isJwtUsable(storedToken)) {
			this.clearSession();
			this.initialized = true;
			return;
		}

		this.token = storedToken;
		try {
			this.user = await apiJson<AuthUser>('auth/me');
		} catch {
			this.clearSession();
		} finally {
			this.initialized = true;
		}
	}

	private async authenticate(path: string, credentials: { email: string; password: string }) {
		return apiJson<AuthResponse>(path, {
			method: 'POST',
			json: credentials
		});
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
