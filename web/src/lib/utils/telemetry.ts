import { SERVER_URL } from '$lib/configs/constants';

export type WebEvent = {
	event_type: 'click' | 'route' | 'pointerdown' | 'change' | 'submit' | 'keyboard' | 'media';
	page_path: string;
	from_path?: string | null;
	target_type: string;
	target_id?: string | null;
	target_label?: string | null;
	target_href?: string | null;
	target_path?: string | null;
	target_context?: Record<string, unknown>;
};

const identityMemory = new Map<string, string>();

function storedId(kind: 'localStorage' | 'sessionStorage', key: string) {
	let value = identityMemory.get(key);
	try {
		const storage = window[kind];
		value = storage.getItem(key) || value || crypto.randomUUID();
		storage.setItem(key, value);
	} catch {}
	value ??= crypto.randomUUID();
	identityMemory.set(key, value);
	return value;
}

function send(path: string, payload: Record<string, unknown>) {
	try {
		if (typeof window === 'undefined') return;
		let token: string | null = null;
		try { token = localStorage.getItem('local-field.access-token'); } catch {}
		const body = JSON.stringify(payload);
		const headers: Record<string, string> = { 'Content-Type': 'application/json' };
		if (token) headers.Authorization = `Bearer ${token}`;
		void fetch(`${SERVER_URL.replace(/\/+$/, '')}/${path}`, {
			method: 'POST', headers, body, keepalive: new TextEncoder().encode(body).byteLength <= 60_000,
			signal: AbortSignal.timeout(5_000)
		}).catch(() => {});
	} catch {}
}

export function trackWebEvent(event: WebEvent) {
	try {
		if (typeof window === 'undefined') return;
		let visitorId: string | undefined;
		let sessionId: string | undefined;
		try {
			visitorId = storedId('localStorage', 'local-field.audit-visitor-id');
			sessionId = storedId('sessionStorage', 'local-field.audit-session-id');
		} catch {}
		send('web/events', {
			...event,
			target_label: event.target_label?.slice(0, 512),
			event_id: crypto.randomUUID(), client_occurred_at: new Date().toISOString(),
			visitor_id: visitorId, session_id: sessionId
		});
	} catch {}
}

function readableLabel(element: Element): string {
	const labels = 'labels' in element ? (element as HTMLInputElement).labels : null;
	const labelledBy = element.getAttribute('aria-labelledby')?.split(/\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' ');
	return ((element.getAttribute('data-audit-label') || element.getAttribute('aria-label') || labelledBy ||
		(labels ? Array.from(labels).map((label) => label.textContent).join(' ') : '') ||
		element.getAttribute('title') || element.getAttribute('alt') ||
		element.getAttribute('name') || element.textContent || element.tagName.toLowerCase()).replace(/\s+/g, ' ').trim() || element.tagName.toLowerCase()).slice(0, 512);
}

export function elementPath(element: Element): string {
	const parts: string[] = [];
	let current: Element | null = element;
	while (current) {
		const parent: Element | null = current.parentElement;
		const siblings: Element[] = parent ? Array.from(parent.children).filter((item) => item.localName === current!.localName) : [];
		parts.unshift(`${current.localName}${current.id ? `#${CSS.escape(current.id)}` : ''}:nth-of-type(${siblings.indexOf(current) + 1 || 1})`);
		if (parent) current = parent;
		else {
			const root = current.getRootNode();
			current = root instanceof ShadowRoot ? root.host : null;
			if (current) parts.unshift('>>>');
		}
	}
	return parts.join(' > ');
}

export function trackElementEvent(event: Event, eventType: WebEvent['event_type'] = 'click') {
	try {
		const path = event.composedPath();
		const element = path.find((node) => node instanceof Element) as Element | undefined;
		if (!element) return;
		const action = path.find((node) => node instanceof Element && node.matches('button, a, input, select, textarea, summary, [role="button"], [role="tab"], [role="option"]')) as Element | undefined;
		const target = action ?? element;
		const targetPath = elementPath(target);
		const scope = target.closest('dialog, [role="dialog"], form, article, section, nav, aside, header, footer');
		const dialog = target.closest('dialog, [role="dialog"]');
		const context: Record<string, unknown> = {
			dialog_path: dialog ? elementPath(dialog) : null,
			dialog_label: dialog?.getAttribute('aria-label') || dialog?.querySelector('h1, h2, h3')?.textContent?.trim().slice(0, 256) || null,
			event_name: event.type, trusted: event.isTrusted,
			ancestors: path.filter((node): node is Element => node instanceof Element).slice(1, 5).map((node) => ({
				tag: node.localName, id: node.id || null,
				label: (node.getAttribute('aria-label') || node.getAttribute('title') || node.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 512)
			})),
			element_tag: element.localName, element_path: elementPath(element),
			target_tag: target.localName, role: target.getAttribute('role'),
			disabled: target.matches(':disabled, [aria-disabled="true"]'),
			target_name: target.getAttribute('name'), input_type: target.getAttribute('type'),
			scope_path: scope ? elementPath(scope) : null,
			scope_label: scope?.getAttribute('aria-label') || scope?.querySelector('h1, h2, h3, legend')?.textContent?.trim().slice(0, 256) || null
		};
		if (event instanceof MouseEvent) Object.assign(context, { x: event.clientX, y: event.clientY, button: event.button });
		if (event instanceof KeyboardEvent) context.key = event.key;
		if (target instanceof HTMLInputElement && ['checkbox', 'radio'].includes(target.type)) context.checked = target.checked;
		if (target instanceof HTMLSelectElement) context.selected_label = target.selectedOptions[0]?.textContent;
		if (target instanceof HTMLMediaElement) Object.assign(context, { current_time: target.currentTime, paused: target.paused, muted: target.muted });
		trackWebEvent({
			event_type: eventType, page_path: `${location.pathname}${location.search}${location.hash}`,
			target_type: target.getAttribute('role') || target.getAttribute('type') || target.localName,
			target_id: target.getAttribute('data-audit-id') || target.id || targetPath,
			target_label: readableLabel(target), target_path: targetPath,
			target_href: target.closest('a')?.getAttribute('href'), target_context: context
		});
	} catch {}
}

export function installInteractionAudit() {
	const listeners: [string, EventListener][] = [];
	const listen = (type: string, handler: EventListener) => {
		document.addEventListener(type, handler, true);
		listeners.push([type, handler]);
	};
	listen('click', (event) => trackElementEvent(event));
	listen('pointerdown', (event) => trackElementEvent(event, 'pointerdown'));
	listen('change', (event) => trackElementEvent(event, 'change'));
	listen('submit', (event) => trackElementEvent(event, 'submit'));
	listen('keydown', (event) => {
		const key = (event as KeyboardEvent).key;
		if (key === 'Enter' || key === 'Escape') trackElementEvent(event, 'keyboard');
	});
	for (const type of ['play', 'pause', 'seeked', 'volumechange', 'ratechange', 'fullscreenchange']) {
		listen(type, (event) => trackElementEvent(event, 'media'));
	}
	return () => listeners.forEach(([type, handler]) => document.removeEventListener(type, handler, true));
}

export function reportApiError(error: unknown, path: string, method: string) {
	try {
		if ((error as { name?: string } | null)?.name === 'AbortError') return;
		const original = error as Error & { response?: Response; data?: unknown; cause?: unknown };
		const payload = {
			page_path: `${location.pathname}${location.search}${location.hash}`, api_path: path, method,
			error_type: original?.name || typeof error, error_message: original?.message || String(error),
			stack: original?.stack, response: original?.data, status_code: original?.response?.status ?? 0,
			client_occurred_at: new Date().toISOString()
		};
		if (original?.response && original.data === undefined && !original.response.bodyUsed) {
			void original.response.clone().text().then((response) => send('web/errors', { ...payload, response })).catch(() => send('web/errors', payload));
		} else send('web/errors', payload);
	} catch {}
}
