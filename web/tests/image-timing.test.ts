import { imageSourceContext, installImageFocusTracking, recordImageCompletion, startImageTiming } from '../src/lib/utils/image-timing';
import { browserFocusContext, installBrowserFocusTracking } from '../src/lib/utils/browser-focus';
import { startApiTiming } from '../src/lib/utils/telemetry';

const result = document.querySelector<HTMLOutputElement>('#result')!;
const originalFetch = window.fetch;
const originalEntries = performance.getEntriesByName.bind(performance);
const originalTimeout = window.setTimeout;
const originalFocus = Object.getOwnPropertyDescriptor(document, 'hasFocus');
const originalVisibility = Object.getOwnPropertyDescriptor(document, 'visibilityState');
const originalHidden = Object.getOwnPropertyDescriptor(document, 'hidden');
let focused = true;
let disposeFocus = () => {};
const metrics: Record<string, any>[] = [];
let checks = 0;
const signed = 'https://storage.example/files/test-file?expires=2000000000&signature=never-log-this';
const pixel = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>';
const delay = (ms: number) => new Promise<void>((resolve) => originalTimeout(resolve, ms));
function assert(condition: unknown, label: string) {
	if (!condition) throw new Error(label);
	checks++;
}
function last() { return metrics.filter((entry) => entry.method === 'IMG' && entry.request_id).at(-1)!; }
function imageFixture() {
	const image = document.createElement('img');
	for (const [name, value] of Object.entries({ src: pixel, currentSrc: pixel, complete: false, naturalWidth: 1, naturalHeight: 1 })) {
		Object.defineProperty(image, name, { value, configurable: true });
	}
	image.loading = 'lazy';
	return image;
}
window.fetch = ((url: string | URL | Request, options: RequestInit) => {
	metrics.push(JSON.parse(String(options.body)));
	return Promise.resolve(new Response(null, { status: 204 }));
}) as typeof fetch;

try {
	Object.defineProperty(document, 'hasFocus', { configurable: true, value: () => focused });
	Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
	Object.defineProperty(document, 'hidden', { configurable: true, value: false });
	disposeFocus = installImageFocusTracking();
	const pageId = browserFocusContext().page_instance_id;
	assert(last().timing_context.focus_event === 'tracking_started' && Boolean(pageId), 'focus tracking starts before generation and has one page identity');
	focused = false;
	window.dispatchEvent(new Event('blur'));
	await delay(15);
	focused = true;
	window.dispatchEvent(new Event('focus'));
	const returned = browserFocusContext();
	assert(returned.last_unfocused_ms! >= 10 && returned.visibility === 'visible', 'app focus interval measured even when tab stays visible');
	assert(returned.last_blur_at && returned.last_focus_at && returned.focus_count === 1 && returned.blur_count === 1, 'focus return keeps prior blur and return times');
	const generation = startApiTiming('generation/image', 'POST');
	const submitted = metrics.at(-1)!;
	assert(submitted.outcome === 'in_progress' && submitted.timing_context.stage === 'generation_request', 'generation request recorded before waiting for response');
	assert(submitted.timing_context.browser_focus_at_start.page_instance_id === pageId && submitted.timing_context.browser_focus_at_start.last_unfocused_ms >= 10, 'generation after return retains app focus history');
	generation.headers(202);
	generation.finish();
	const events = startApiTiming('generation/image/prompt-id/events?client_id=test', 'GET', true);
	events.headers(200);
	events.firstByte();
	events.finish();
	assert(metrics.at(-1)!.timing_context.stage === 'generation_events' && metrics.at(-1)!.timing_context.browser_focus.page_instance_id === pageId, 'generation SSE joins to same page focus history');
	const afterReturn = startImageTiming(signed, 'external');
	afterReturn.ready(pixel);
	const returnedImage = imageFixture();
	afterReturn.observe(returnedImage);
	returnedImage.dispatchEvent(new Event('load'));
	assert(last().timing_context.browser_focus_at_start.last_unfocused_ms >= 10 && last().timing_context.unfocused_during_load_ms === 0, 'prior app switch distinguished from a switch during image loading');
	const duringLoad = startImageTiming(signed, 'external');
	const duringId = last().request_id;
	duringLoad.ready(pixel);
	const waitingImage = imageFixture();
	duringLoad.observe(waitingImage);
	focused = false;
	window.dispatchEvent(new Event('blur'));
	await delay(15);
	focused = true;
	window.dispatchEvent(new Event('focus'));
	waitingImage.dispatchEvent(new Event('load'));
	const duringMetric = metrics.findLast((entry) => entry.request_id === duringId)!;
	assert(duringMetric.timing_context.unfocused_during_load_ms >= 10 && duringMetric.timing_context.hidden_ms === 0, 'blur duration and hidden tab duration measured independently');
	assert(duringMetric.timing_context.browser_focus_at_start.focus_count === 1 && duringMetric.timing_context.browser_focus.focus_count === 2, 'start focus snapshot stays immutable across load');
	const sequence = browserFocusContext().transition_sequence;
	document.createElement('input').dispatchEvent(new Event('blur', { bubbles: true }));
	window.dispatchEvent(new Event('focus'));
	assert(browserFocusContext().transition_sequence === sequence, 'element and duplicate focus events do not create fake app switches');
	for (let index = 0; index < 8; index++) {
		focused = false; window.dispatchEvent(new Event('blur'));
		focused = true; window.dispatchEvent(new Event('focus'));
	}
	assert(browserFocusContext().recent_transitions?.length === 12 && browserFocusContext().transition_sequence! > 12, 'focus history is bounded while counters retain all transitions');
	const sharedDispose = installBrowserFocusTracking();
	sharedDispose();
	sharedDispose();
	assert(browserFocusContext().tracking_active && browserFocusContext().page_instance_id === pageId, 'shared install cleanup is idempotent and keeps root tracker active');
	const context = imageSourceContext(signed);
	assert(context.file_id === 'test-file' && context.source_path === 'https://storage.example/files/test-file', 'stable file ID and query-free source');
	assert(context.url_expires_at_ms === 2000000000000, 'signed URL expiry recorded without signature');
	assert(imageSourceContext(pixel).source_path === 'data:image', 'inline image bytes never recorded');
	const timing = startImageTiming(signed, 'external');
	const requestId = last().request_id;
	assert(last().outcome === 'in_progress' && last().finished_at === undefined, 'start visible before load finishes');
	timing.ready(pixel);
	const image = imageFixture();
	timing.observe(image);
	image.dispatchEvent(new Event('load'));
	assert(last().request_id === requestId && last().outcome === 'completed', 'one trace connects start and success');
	assert(last().status_code === 0 && last().timing_context.resource_timing === 'missing', 'unobserved HTTP status remains unknown');
	assert(last().timing_context.natural_width === 1 && last().timing_context.loading === 'lazy', 'dimensions and lazy loading recorded');
	const count = metrics.length;
	image.dispatchEvent(new Event('error'));
	timing.dispose();
	assert(metrics.length === count, 'completion removes listeners and prevents duplicate terminal records');

	for (const restricted of [false, true]) {
		const trace = startImageTiming(signed, 'external');
		trace.ready(pixel);
		const start = performance.now();
		performance.getEntriesByName = (() => [{
			name: pixel, entryType: 'resource', toJSON: () => ({}), initiatorType: 'img', startTime: start, duration: 30,
			domainLookupStart: restricted ? 0 : start, domainLookupEnd: restricted ? 0 : start + 2,
			connectStart: restricted ? 0 : start + 2, connectEnd: restricted ? 0 : start + 5,
			requestStart: restricted ? 0 : start + 5, responseStart: restricted ? 0 : start + 20,
			responseEnd: start + 30, responseStatus: restricted ? 0 : 200,
			transferSize: 0, encodedBodySize: restricted ? 0 : 40, decodedBodySize: restricted ? 0 : 80,
			nextHopProtocol: restricted ? '' : 'h2'
		}]) as typeof performance.getEntriesByName;
		const element = imageFixture();
		trace.observe(element);
		await delay(40);
		element.dispatchEvent(new Event('load'));
		const recorded = last().timing_context;
		assert(recorded.resource_timing === (restricted ? 'restricted' : 'full'), 'cross-origin timing visibility distinguished');
		assert(recorded.download_ms === (restricted ? null : 10), 'hidden cross-origin phases are null, never fake zero timings');
		assert(recorded.cache_state === (restricted ? 'unknown' : 'local_cache'), 'cache evidence requires exposed sizes');
		assert(recorded.after_response_ms >= 0 && recorded.request_start_delay_ms >= 0, 'request delay and post-response processing split');
	}
	performance.getEntriesByName = originalEntries;

	const failed = startImageTiming(signed, 'external');
	failed.ready(pixel);
	const broken = imageFixture();
	failed.observe(broken);
	broken.dispatchEvent(new Event('error'));
	assert(last().outcome === 'error' && last().timing_context.error_type === 'ImageLoadError', 'native image failure recorded');
	assert(metrics.some((entry) => entry.error_type === 'ImageLoadError'), 'native failures reach error logs');

	const fetching = startImageTiming('/vault/images/example/source', 'server');
	fetching.fail(new Error('synthetic blob failure'));
	assert(last().timing_context.failure_phase === 'source_fetch', 'Blob fetch failure distinguished from native decode failure');

	window.setTimeout = ((handler: TimerHandler, timeout?: number, ...args: any[]) => originalTimeout(handler, timeout === 10000 || timeout === 30000 ? 5 : timeout, ...args)) as typeof window.setTimeout;
	const slow = startImageTiming(signed, 'external');
	const slowId = last().request_id;
	await delay(20);
	assert(metrics.filter((entry) => entry.request_id === slowId).length === 3, 'bounded slow checkpoints emitted without aborting load');
	assert(last().outcome === 'in_progress' && last().timing_context.slow_threshold_ms === 30000, 'slow load stays pending instead of inventing a timeout');
	slow.dispose();
	assert(last().outcome === 'cancelled', 'unmounted pending image recorded as cancellation');
	window.setTimeout = originalTimeout;

	const cached = new Image();
	await new Promise<void>((resolve, reject) => { cached.onload = () => resolve(); cached.onerror = reject; cached.src = pixel; });
	const cachedTrace = startImageTiming(signed, 'external', 'gallery');
	cachedTrace.ready(pixel);
	cachedTrace.observe(cached);
	await delay(0);
	assert(last().outcome === 'completed' && last().timing_context.view === 'gallery', 'already loaded native image and gallery traced');

	recordImageCompletion(signed, 'prompt-id', 'generation-id');
	assert(last().timing_context.stage === 'generation_result_received' && last().timing_context.prompt_id === 'prompt-id', 'generation delivery joins to stable image file ID');
	assert(last().timing_context.browser_focus.page_instance_id === pageId && last().timing_context.browser_focus.last_focus_at, 'generation result keeps focus history from before generation');
	recordImageCompletion(undefined, 'missing-image', 'generation-id');
	assert(last().timing_context.has_image_url === false, 'completion without image URL is visible');
	assert(!JSON.stringify(metrics).includes('never-log-this') && !JSON.stringify(metrics).includes('<svg'), 'signed credentials and image bytes excluded from every log');
	window.fetch = (() => { throw new Error('logging offline'); }) as typeof fetch;
	const offline = startImageTiming(signed, 'external');
	offline.dispose();
	assert(true, 'logging failure cannot break image lifecycle');
	disposeFocus();
	disposeFocus();
	assert(!browserFocusContext().tracking_active, 'root disposal removes focus tracking');
	const disposedCount = metrics.length;
	window.dispatchEvent(new Event('blur'));
	assert(metrics.length === disposedCount, 'disposed global focus tracker sends no events');
	result.textContent = `${checks} image timing checks passed`;
	result.dataset.status = 'passed';
} catch (error) {
	result.textContent = error instanceof Error ? `${error.message}\n${error.stack}` : String(error);
	result.dataset.status = 'failed';
	throw error;
} finally {
	disposeFocus();
	for (const [name, descriptor] of [['hasFocus', originalFocus], ['visibilityState', originalVisibility], ['hidden', originalHidden]] as const) {
		if (descriptor) Object.defineProperty(document, name, descriptor);
		else Reflect.deleteProperty(document, name);
	}
	window.fetch = originalFetch;
	window.setTimeout = originalTimeout;
	performance.getEntriesByName = originalEntries;
}
