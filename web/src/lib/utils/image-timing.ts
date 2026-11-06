import { SERVER_URL } from '$lib/configs/constants';
import { recordImageTiming, reportApiError } from './telemetry';
import { browserFocusContext, installBrowserFocusTracking } from './browser-focus';

type ImageTiming = {
	ready: (displayedSource: string, bytes?: number) => void;
	observe: (image: HTMLImageElement) => () => void;
	fail: (error: unknown) => void;
	dispose: () => void;
};

export function installImageFocusTracking() {
	return installBrowserFocusTracking((focus, event) => {
		try {
			const at = new Date().toISOString();
			recordImageTiming({
				request_id: crypto.randomUUID(), api_path: 'browser.focus',
				page_path: `${location.pathname}${location.search}${location.hash}`,
				requested_at: at, finished_at: at, duration_ms: 0, status_code: 0, outcome: 'completed',
				timing_context: { category: 'image', stage: 'browser_focus_change', focus_event: event, browser_focus: focus }
			});
		} catch {}
	});
}

export function imageSourceContext(source: string) {
	try {
		const url = new URL(source, `${SERVER_URL.replace(/\/+$/, '')}/`);
		if (!['http:', 'https:'].includes(url.protocol)) return { source_path: `${url.protocol}image` };
		const expires = Number(url.searchParams.get('expires'));
		return {
			source_path: `${url.origin}${url.pathname}`,
			file_id: url.pathname.match(/\/files\/([^/]+)/)?.[1],
			prompt_id: url.pathname.match(/\/generation\/image\/([^/]+)\//)?.[1],
			url_expires_at_ms: Number.isFinite(expires) && expires > 0 ? expires * (expires < 1e12 ? 1000 : 1) : undefined
		};
	} catch { return { source_path: 'image:invalid-url' }; }
}

export function recordImageCompletion(source: string | undefined, promptId: string, generationId: string) {
	try {
		const at = new Date().toISOString();
		const context = imageSourceContext(source ?? 'image:missing-url');
		recordImageTiming({
			request_id: crypto.randomUUID(), api_path: context.source_path,
			page_path: `${location.pathname}${location.search}${location.hash}`,
			requested_at: at, finished_at: at, duration_ms: 0, status_code: 0, outcome: 'completed',
			timing_context: { ...context, category: 'image', stage: 'generation_result_received',
				prompt_id: promptId, generation_id: generationId, has_image_url: Boolean(source), browser_focus: browserFocusContext() }
		});
	} catch {}
}

function resourceTiming(source: string, assignedAt: number, observedAt: number) {
	try {
		const entry = (performance.getEntriesByName(source, 'resource') as PerformanceResourceTiming[])
			.filter((item) => item.initiatorType === 'img' && item.startTime >= assignedAt - 1).at(-1);
		if (!entry) return { resource_timing: 'missing' };
		const exposed = entry.responseStart > 0 && entry.requestStart > 0;
		return {
			resource_timing: exposed ? 'full' : 'restricted',
			resource_duration_ms: entry.duration,
			request_start_delay_ms: Math.max(0, entry.startTime - assignedAt),
			dns_ms: exposed ? Math.max(0, entry.domainLookupEnd - entry.domainLookupStart) : null,
			connect_ms: exposed ? Math.max(0, entry.connectEnd - entry.connectStart) : null,
			response_wait_ms: exposed ? Math.max(0, entry.responseStart - entry.requestStart) : null,
			download_ms: exposed ? Math.max(0, entry.responseEnd - entry.responseStart) : null,
			after_response_ms: Math.max(0, observedAt - entry.responseEnd),
			response_status: entry.responseStatus || null,
			transfer_bytes: exposed ? entry.transferSize : null,
			encoded_bytes: exposed ? entry.encodedBodySize : null,
			decoded_bytes: exposed ? entry.decodedBodySize : null,
			cache_state: exposed ? entry.transferSize === 0 && entry.decodedBodySize > 0 ? 'local_cache' : 'network' : 'unknown',
			next_hop_protocol: entry.nextHopProtocol || null,
			headers_from_start_ms: exposed ? Math.max(0, entry.responseStart - assignedAt) : undefined
		};
	} catch { return { resource_timing: 'unavailable' }; }
}

function createImageTiming(source: string, sourceType: string, view: string): ImageTiming {
	const start = performance.now();
	const requestedAt = new Date().toISOString();
	const pagePath = `${location.pathname}${location.search}${location.hash}`;
	const requestId = crypto.randomUUID();
	const sourceContext = imageSourceContext(source);
	const focusAtStart = browserFocusContext();
	const context: Record<string, unknown> = {
		...sourceContext, category: 'image', stage: 'image_load', source_type: sourceType, view,
		browser_focus_at_start: focusAtStart,
		visibility_at_start: document.visibilityState,
		url_valid_for_ms: sourceContext.url_expires_at_ms === undefined ? undefined : sourceContext.url_expires_at_ms - Date.now()
	};
	let assignedAt = start;
	let displayedSource = source;
	let image: HTMLImageElement | undefined;
	let inViewport: boolean | null = null;
	let finished = false;
	let detach = () => {};
	let hiddenAt: number | undefined = document.hidden ? start : undefined;
	let hiddenMs = 0;
	const visibility = () => {
		if (document.hidden && hiddenAt === undefined) hiddenAt = performance.now();
		else if (!document.hidden && hiddenAt !== undefined) {
			hiddenMs += performance.now() - hiddenAt;
			hiddenAt = undefined;
		}
	};
	document.addEventListener('visibilitychange', visibility);
	const timers: ReturnType<typeof setTimeout>[] = [];
	const record = (outcome: 'in_progress' | 'completed' | 'error' | 'cancelled') => {
		try {
			const now = performance.now();
			const resource = resourceTiming(image?.currentSrc || displayedSource, assignedAt, now);
			const focus = browserFocusContext();
			recordImageTiming({
				request_id: requestId, api_path: sourceContext.source_path, page_path: pagePath,
				requested_at: requestedAt, finished_at: outcome === 'in_progress' ? undefined : new Date().toISOString(),
				duration_ms: outcome === 'in_progress' ? undefined : now - start,
				headers_ms: resource.headers_from_start_ms === undefined ? undefined : assignedAt - start + resource.headers_from_start_ms,
				status_code: resource.response_status ?? 0, outcome,
				timing_context: {
					...context, ...resource, elapsed_ms: now - start, visibility: document.visibilityState,
					browser_focus: focus,
					unfocused_during_load_ms: focus.tracking_active && focusAtStart.tracking_active
						? Math.max(0, (focus.unfocused_total_ms ?? 0) - (focusAtStart.unfocused_total_ms ?? 0)) : null,
					hidden_ms: hiddenMs + (hiddenAt === undefined ? 0 : now - hiddenAt),
					document_has_focus: document.hasFocus(), loading: image?.loading,
					in_viewport: inViewport,
					image_complete: image?.complete, natural_width: image?.naturalWidth, natural_height: image?.naturalHeight
				}
			});
		} catch {}
	};
	const finish = (outcome: 'completed' | 'error' | 'cancelled', error?: unknown) => {
		if (finished) return;
		finished = true;
		if (error instanceof Error) context.error_type = error.name;
		record(outcome);
		timers.forEach(clearTimeout);
		document.removeEventListener('visibilitychange', visibility);
		detach();
	};
	record('in_progress');
	for (const threshold of [10_000, 30_000]) timers.push(setTimeout(() => {
		if (finished) return;
		context.slow_threshold_ms = threshold;
		context.watchdog_delay_ms = Math.max(0, performance.now() - start - threshold);
		record('in_progress');
	}, threshold));
	return {
		ready(displayed, bytes) {
			try {
				assignedAt = performance.now();
				displayedSource = new URL(displayed, location.href).href;
				context.source_ready_ms = assignedAt - start;
				if (bytes !== undefined) context.blob_bytes = bytes;
			} catch {}
		},
		observe(element) {
			image = element;
			inViewport = null;
			const loaded = () => { if (element.src === displayedSource) finish('completed'); };
			const failed = () => {
				if (finished || element.src !== displayedSource) return;
				const error = new Error('Image resource failed to load or decode');
				error.name = 'ImageLoadError';
				finish('error', error);
				reportApiError(error, sourceContext.source_path, 'IMG');
			};
			element.addEventListener('load', loaded);
			element.addEventListener('error', failed);
			let observer: IntersectionObserver | undefined;
			try {
				observer = new IntersectionObserver((entries) => {
					inViewport = entries.at(-1)?.isIntersecting ?? null;
					if (inViewport && context.first_visible_ms === undefined) {
						context.first_visible_ms = performance.now() - start;
					}
				});
				observer.observe(element);
			} catch {}
			detach = () => {
				element.removeEventListener('load', loaded);
				element.removeEventListener('error', failed);
				observer?.disconnect();
			};
			if (element.complete && element.currentSrc === displayedSource) queueMicrotask(() => {
				if (!finished) element.naturalWidth > 0 ? loaded() : failed();
			});
			return detach;
		},
		fail(error) { context.failure_phase = 'source_fetch'; finish('error', error); },
		dispose() { finish('cancelled'); }
	};
}

export function startImageTiming(source: string, sourceType: string, view = 'inline'): ImageTiming {
	try { return createImageTiming(source, sourceType, view); }
	catch { return { ready() {}, observe() { return () => {}; }, fail() {}, dispose() {} }; }
}
