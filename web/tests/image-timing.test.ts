import { imageSourceContext, recordImageCompletion, startImageTiming } from '../src/lib/utils/image-timing';

const result = document.querySelector<HTMLOutputElement>('#result')!;
const originalFetch = window.fetch;
const originalEntries = performance.getEntriesByName.bind(performance);
const originalTimeout = window.setTimeout;
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
	recordImageCompletion(undefined, 'missing-image', 'generation-id');
	assert(last().timing_context.has_image_url === false, 'completion without image URL is visible');
	assert(!JSON.stringify(metrics).includes('never-log-this') && !JSON.stringify(metrics).includes('<svg'), 'signed credentials and image bytes excluded from every log');
	window.fetch = (() => { throw new Error('logging offline'); }) as typeof fetch;
	const offline = startImageTiming(signed, 'external');
	offline.dispose();
	assert(true, 'logging failure cannot break image lifecycle');
	result.textContent = `${checks} image timing checks passed`;
	result.dataset.status = 'passed';
} catch (error) {
	result.textContent = error instanceof Error ? `${error.message}\n${error.stack}` : String(error);
	result.dataset.status = 'failed';
	throw error;
} finally {
	window.fetch = originalFetch;
	window.setTimeout = originalTimeout;
	performance.getEntriesByName = originalEntries;
}
