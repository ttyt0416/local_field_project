type FocusEventName = 'focus' | 'blur' | 'visibilitychange';
type Transition = {
	sequence: number;
	event: FocusEventName;
	at: string;
	elapsed_ms: number;
	visibility: DocumentVisibilityState;
	document_has_focus: boolean;
	trusted: boolean;
};
type FocusState = {
	pageId: string;
	startedAt: string;
	start: number;
	focused: boolean;
	unfocusedSince?: number;
	unfocusedTotal: number;
	lastUnfocusedMs: number | null;
	lastBlur?: { at: string; time: number };
	lastFocus?: { at: string; time: number };
	blurCount: number;
	focusCount: number;
	sequence: number;
	transitions: Transition[];
};

let state: FocusState | undefined;
let installations = 0;
let removeListeners = () => {};
const subscribers = new Set<(context: ReturnType<typeof browserFocusContext>, event: string) => void>();

export function browserFocusContext() {
	try {
		if (!state || typeof document === 'undefined') return { tracking_active: false };
		const now = performance.now();
		return {
			tracking_active: installations > 0, page_instance_id: state.pageId,
			tracking_started_at: state.startedAt, observed_at: new Date().toISOString(),
			page_elapsed_ms: now - state.start, document_has_focus: document.hasFocus(),
			tracked_focus: state.focused, visibility: document.visibilityState,
			blur_count: state.blurCount, focus_count: state.focusCount,
			last_blur_at: state.lastBlur?.at ?? null, last_focus_at: state.lastFocus?.at ?? null,
			since_last_blur_ms: state.lastBlur ? now - state.lastBlur.time : null,
			since_last_focus_ms: state.lastFocus ? now - state.lastFocus.time : null,
			last_unfocused_ms: state.lastUnfocusedMs,
			unfocused_total_ms: state.unfocusedTotal + (state.unfocusedSince === undefined ? 0 : now - state.unfocusedSince),
			transition_sequence: state.sequence, recent_transitions: state.transitions.slice()
		};
	} catch { return { tracking_active: false }; }
}

export function installBrowserFocusTracking(onChange?: (context: ReturnType<typeof browserFocusContext>, event: string) => void) {
	try {
		if (typeof window === 'undefined') return () => {};
		if (installations === 0) {
			const start = performance.now();
			const focused = document.hasFocus();
			state = {
				pageId: crypto.randomUUID(), startedAt: new Date().toISOString(), start, focused,
				unfocusedSince: focused ? undefined : start, unfocusedTotal: 0, lastUnfocusedMs: null,
				blurCount: 0, focusCount: 0, sequence: 0, transitions: []
			};
			const changed = (event: Event) => {
				try {
					if (!state || (event.type !== 'visibilitychange' && event.target !== window)) return;
					const name = event.type as FocusEventName;
					const now = performance.now();
					const at = new Date().toISOString();
					if (name === 'blur') {
						if (!state.focused) return;
						state.focused = false;
						state.unfocusedSince = now;
						state.lastBlur = { at, time: now };
						state.blurCount++;
					} else if (name === 'focus') {
						if (state.focused) return;
						state.focused = true;
						if (state.unfocusedSince !== undefined) {
							state.lastUnfocusedMs = now - state.unfocusedSince;
							state.unfocusedTotal += state.lastUnfocusedMs;
							state.unfocusedSince = undefined;
						}
						state.lastFocus = { at, time: now };
						state.focusCount++;
					}
					state.transitions.push({
						sequence: ++state.sequence, event: name, at, elapsed_ms: now - state.start,
						visibility: document.visibilityState, document_has_focus: document.hasFocus(), trusted: event.isTrusted
					});
					if (state.transitions.length > 12) state.transitions.shift();
					for (const callback of subscribers) {
						try { callback(browserFocusContext(), name); } catch {}
					}
				} catch {}
			};
			window.addEventListener('blur', changed);
			window.addEventListener('focus', changed);
			document.addEventListener('visibilitychange', changed);
			removeListeners = () => {
				window.removeEventListener('blur', changed);
				window.removeEventListener('focus', changed);
				document.removeEventListener('visibilitychange', changed);
			};
		}
		installations++;
		if (onChange) {
			subscribers.add(onChange);
			try { onChange(browserFocusContext(), 'tracking_started'); } catch {}
		}
		let disposed = false;
		return () => {
			if (disposed) return;
			disposed = true;
			if (onChange) subscribers.delete(onChange);
			if (--installations === 0) {
				removeListeners();
				state = undefined;
			}
		};
	} catch { return () => {}; }
}
