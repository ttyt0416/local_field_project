import { browser } from '$app/environment';

export const THEME_KEY = 'local-field.theme';

type Theme = 'dark' | 'light';

class ThemeStore {
	isDark = $state(true);

	initialize() {
		if (!browser) return;
		const savedTheme = localStorage.getItem(THEME_KEY);
		this.setTheme(savedTheme === 'light' ? 'light' : 'dark', false);
	}

	toggle() {
		this.setTheme(this.isDark ? 'light' : 'dark');
	}

	private setTheme(theme: Theme, persist = true) {
		this.isDark = theme === 'dark';
		if (!browser) return;
		document.documentElement.classList.toggle('dark', this.isDark);
		if (persist) localStorage.setItem(THEME_KEY, theme);
	}
}

export const themeStore = new ThemeStore();
