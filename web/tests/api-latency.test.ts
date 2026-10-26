import { apiJson, apiForm, apiBlob, apiDelete, streamSse } from '../src/lib/utils/api';
import { downloadMedia } from '../src/lib/utils/download';

const result = document.querySelector<HTMLOutputElement>('#result')!;
const originalFetch = window.fetch;
const metrics: Record<string, any>[] = [];
let checks = 0;
let telemetryMode: 'normal' | 'reject' | 'pending' = 'normal';
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
function assert(condition: unknown, label: string) {
	if (!condition) throw new Error(label);
	checks++;
	result.textContent = `Checking: ${label}`;
}
function last(path: string) { return metrics.filter((metric) => metric.api_path === path).at(-1)!; }
window.fetch = (async (input: RequestInfo | URL, options?: RequestInit) => {
	const request = input instanceof Request ? input : new Request(input, options);
	const path = new URL(request.url).pathname;
	if (path.endsWith('/web/api-timings')) {
		metrics.push(await request.json());
		if (telemetryMode === 'pending') return new Promise<Response>(() => {});
		if (telemetryMode === 'reject') throw new Error('logging offline');
		return new Response(null, { status: 204 });
	}
	if (path.endsWith('/web/errors')) return new Response(null, { status: 204 });
	if (path.endsWith('/network')) throw new TypeError('original fetch failure');
	if (path.endsWith('/abort')) throw new DOMException('original abort', 'AbortError');
	if (path.endsWith('/timeout')) return new Promise<Response>(() => {});
	if (path.endsWith('/json')) assert(request.headers.get('accept') === 'application/json', 'JSON Accept header preserved');
	await delay(12);
	if (path.endsWith('/delete')) return new Response(null, { status: 204 });
	if (path.endsWith('/blob')) return new Response(new Uint8Array([1, 2, 3, 4]));
	if (path.endsWith('/form')) {
		assert(request.method === 'POST' && request.headers.get('content-type')?.startsWith('multipart/form-data'), 'FormData request preserved');
		return Response.json({ ok: true });
	}
	if (path.endsWith('/invalid-json')) return new Response('original invalid json');
	if (path.endsWith('/sse') || path.endsWith('/broken-sse')) {
		const body = new ReadableStream({ start(controller) {
			setTimeout(() => {
				controller.enqueue(new TextEncoder().encode('event: status\ndata: {"status":"processing"}\n\n'));
				setTimeout(() => path.endsWith('/broken-sse') ? controller.error(new Error('original stream reset')) : controller.close(), 25);
			}, 25);
		} });
		return new Response(body, { headers: { 'Content-Type': 'text/event-stream' } });
	}
	const body = new ReadableStream({ start(controller) {
		setTimeout(() => { controller.enqueue(new TextEncoder().encode('{"ok":true,"detail":"original provider error"}')); controller.close(); }, 25);
	} });
	return new Response(body, { status: path.endsWith('/http-error') ? 503 : 200, headers: { 'Content-Type': 'application/json' } });
}) as typeof fetch;

try {
	const prefix = 'latency-fixture/';
	result.textContent = 'Requesting JSON';
	assert((await apiJson<{ ok: boolean }>(prefix + 'json')).ok, 'JSON result preserved');
	await delay(0);
	assert(last(prefix + 'json').duration_ms > last(prefix + 'json').headers_ms + 10, 'JSON duration includes body read');
	assert(last(prefix + 'json').outcome === 'completed' && last(prefix + 'json').status_code === 200, 'successful API latency');
	assert((await apiForm<{ ok: boolean }>(prefix + 'form', new FormData())).ok, 'form result preserved');
	assert((await apiBlob(prefix + 'blob')).size === 4, 'blob result preserved');
	await apiDelete(prefix + 'delete');
	await delay(0);
	for (const name of ['form', 'blob', 'delete']) assert(last(prefix + name).duration_ms >= last(prefix + name).headers_ms, `${name} latency recorded`);
	let customHook = false;
	await apiJson(prefix + 'custom-hook', { hooks: { afterResponse: [() => { customHook = true; }] } });
	assert(customHook, 'existing response hooks preserved');
	const parsed = await apiJson<{ custom: boolean }>(prefix + 'custom-json', { parseJson: () => ({ custom: true }) });
	assert(parsed.custom, 'custom JSON parsing preserved');
	for (const [name, outcome] of [['http-error', 'http_error'], ['invalid-json', 'error'], ['network', 'error'], ['abort', 'cancelled'], ['timeout', 'timeout']]) {
		let thrown: unknown;
		try { await apiJson(prefix + name, { timeout: name === 'timeout' ? 15 : 1000 }); } catch (error) { thrown = error; }
		assert(thrown instanceof Error && thrown.cause instanceof Error, `${name}: original exception cause preserved`);
		await delay(0);
		assert(last(prefix + name).outcome === outcome && last(prefix + name).duration_ms >= 0, `${name}: failure latency recorded`);
	}
	assert(last(prefix + 'http-error').status_code === 503 && last(prefix + 'network').status_code === 0, 'HTTP and network failures distinguished');
	let events = 0;
	await streamSse(prefix + 'sse', () => { events++; });
	await delay(0);
	const stream = metrics.filter((metric) => metric.api_path === prefix + 'sse');
	assert(events === 1 && stream.length === 3, 'SSE headers, first chunk and completion recorded');
	assert(stream[0].outcome === 'in_progress' && stream[1].first_byte_ms >= stream[0].headers_ms, 'SSE phases available while open');
	assert(stream[2].duration_ms > stream[2].first_byte_ms + 10 && stream[2].outcome === 'completed', 'SSE connection lifetime separated from first response');
	assert(new Set(stream.map((metric) => metric.request_id)).size === 1, 'SSE phases correlate to one row');
	try { await streamSse(prefix + 'broken-sse', () => {}); } catch {}
	await delay(0);
	assert(last(prefix + 'broken-sse').outcome === 'error' && last(prefix + 'broken-sse').status_code === 200, 'stream reset after headers retains latency and actual HTTP status');
	const click = HTMLAnchorElement.prototype.click;
	try {
		HTMLAnchorElement.prototype.click = () => {};
		await downloadMedia('https://external.test/latency-fixture/blob', 'probe.bin');
		await delay(0);
		assert(last('https://external.test/latency-fixture/blob').status_code === 200, 'external download latency recorded');
		try { await downloadMedia('https://external.test/latency-fixture/http-error', 'probe.bin'); } catch {}
		await delay(0);
		assert(last('https://external.test/latency-fixture/http-error').outcome === 'http_error', 'external download HTTP error latency recorded');
	} finally { HTMLAnchorElement.prototype.click = click; }
	telemetryMode = 'reject';
	assert((await apiJson<{ ok: boolean }>(prefix + 'audit-reject')).ok, 'logging failure does not affect API result');
	telemetryMode = 'pending';
	const completed = await Promise.race([apiJson<{ ok: boolean }>(prefix + 'audit-slow').then((value) => value.ok), delay(200).then(() => false)]);
	assert(completed, 'API never waits for logging completion');
	result.textContent = `${checks} API latency checks passed`;
	result.dataset.status = 'passed';
} catch (error) {
	result.textContent = error instanceof Error ? `${error.message}\n${error.stack}` : String(error);
	result.dataset.status = 'failed';
	throw error;
} finally {
	window.fetch = originalFetch;
}
