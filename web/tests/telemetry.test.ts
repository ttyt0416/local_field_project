import { installInteractionAudit, trackWebEvent, reportApiError, elementPath } from '../src/lib/utils/telemetry';

const fixture = document.querySelector<HTMLElement>('#fixture')!;
const result = document.querySelector<HTMLOutputElement>('#result')!;
const requests: { url: string; body: Record<string, any>; options: RequestInit }[] = [];
const originalFetch = window.fetch;
const originalPath = location.href;
const originalToken = localStorage.getItem('local-field.access-token');
let checks = 0;
function assert(condition: unknown, label: string) {
	if (!condition) throw new Error(label);
	checks++;
}
function latest() { return requests.at(-1)!.body; }
window.fetch = ((url: string | URL | Request, options: RequestInit) => {
	requests.push({ url: String(url), body: JSON.parse(String(options.body)), options });
	return Promise.resolve(new Response(null, { status: 204 }));
}) as typeof fetch;
const dispose = installInteractionAudit();
try {
	localStorage.setItem('local-field.access-token', 'synthetic-audit-token');
	fixture.innerHTML = '<dialog open><header><h2>모델 폴더 선택</h2><button aria-label="닫기"><svg><path /></svg></button></header><label for="audit-checkbox">모델 선택</label><input id="audit-checkbox" type="checkbox"><select aria-label="모델"><option>MiniMax</option><option selected>MOSS</option></select><button disabled>설치 중</button><a href="#test"><span>상세</span></a><p>본문</p><input type="password" value="never-record-this"><form><button type="submit">저장</button></form><video></video><model-viewer aria-label="3D 뷰어"></model-viewer></dialog>';
	fixture.querySelector('path')!.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
	assert(latest().target_label === '닫기', 'nested SVG must identify its button');
	assert(latest().target_context.element_tag === 'path', 'actual clicked element retained');
	assert(latest().target_context.dialog_label === '모델 폴더 선택', 'dialog heading distinguishes repeated buttons');
	assert(latest().target_id && latest().target_path.includes('button'), 'missing ID receives exact DOM path');
	assert(Boolean(latest().event_id && latest().client_occurred_at && latest().visitor_id && latest().session_id), 'event identity and precise client time');
	assert((requests.at(-1)!.options.headers as Record<string, string>).Authorization === 'Bearer synthetic-audit-token', 'who is authenticated by server');
	const visitor = latest().visitor_id;
	const session = latest().session_id;
	const pages = ['/', '/login', '/models', '/files', '/presets', '/prompts', '/tags', '/uploads', '/uploads/sample', '/vault', '/vault/images/sample', '/vault/videos/sample', '/vault/3d/sample', '/generate/image', '/generate/image-to-image', '/generate/video', '/generate/music', '/generate/3d'];
	for (const page of pages) {
		history.replaceState({}, '', page + '?test=1#position');
		fixture.querySelector('p')!.click();
		assert(latest().page_path === page + '?test=1#position' && latest().target_type === 'p', `plain element captured on ${page}`);
		assert(latest().visitor_id === visitor && latest().session_id === session, 'visitor and session persist across routes');
	}
	const checkbox = fixture.querySelector<HTMLInputElement>('input[type=checkbox]')!;
	checkbox.checked = true;
	checkbox.dispatchEvent(new Event('change', { bubbles: true }));
	assert(latest().target_label === '모델 선택' && latest().target_context.checked === true, 'associated checkbox label and state');
	fixture.querySelector('select')!.dispatchEvent(new Event('change', { bubbles: true }));
	assert(latest().target_context.selected_label === 'MOSS', 'native select keyboard change');
	fixture.querySelector('button[disabled]')!.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
	assert(latest().event_type === 'pointerdown' && latest().target_label === '설치 중', 'disabled targets and pointer interaction');
	fixture.querySelector('a span')!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
	assert(latest().target_href === '#test' && latest().target_label === '상세', 'link and nested text');
	fixture.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
	assert(latest().event_type === 'submit', 'keyboard submit');
	fixture.querySelector('dialog')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
	assert(latest().event_type === 'keyboard' && latest().target_context.key === 'Escape', 'keyboard dialog close');
	fixture.querySelector('video')!.dispatchEvent(new Event('pause'));
	assert(latest().event_type === 'media', 'non-bubbling native media controls');
	const shadow = fixture.querySelector('model-viewer')!.attachShadow({ mode: 'open' });
	shadow.innerHTML = '<button aria-label="카메라"><span>뷰</span></button>';
	shadow.querySelector('span')!.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
	assert(latest().target_label === '카메라' && latest().target_path.includes('>>>'), '3D viewer shadow DOM');
	assert(latest().target_context.element_path.includes('span'), 'shadow actual clicked span');
	assert(elementPath(fixture.querySelector('button')!) !== elementPath(fixture.querySelector('button[disabled]')!), 'same-tag sibling identity');
	fixture.querySelector('input[type=password]')!.dispatchEvent(new Event('change', { bubbles: true }));
	assert(!JSON.stringify(latest()).includes('never-record-this'), 'password/input values never captured');
	trackWebEvent({ event_type: 'route', page_path: '/generate/music?mode=1', from_path: '/generate/3d', target_type: 'route', target_context: { navigation_type: 'popstate' } });
	assert(latest().from_path === '/generate/3d' && latest().target_context.navigation_type === 'popstate', 'route from, to and navigation type');
	reportApiError(Object.assign(new Error('upstream raw error'), { response: new Response(null, { status: 502 }), data: { detail: 'original body' } }), '/generation/music', 'POST');
	assert(requests.at(-1)!.url.endsWith('/web/errors') && latest().error_message === 'upstream raw error' && latest().response.detail === 'original body', 'original API error response');
	const count = requests.length;
	reportApiError(new DOMException('cancelled', 'AbortError'), '/api', 'GET');
	assert(requests.length === count, 'intentional abort excluded');
	trackWebEvent({ event_type: 'route', page_path: '/' + 'a'.repeat(64000), target_type: 'route' });
	assert(requests.at(-1)!.options.keepalive === false, 'large record avoids keepalive byte limit');
	window.fetch = (() => Promise.reject(new Error('logging offline'))) as typeof fetch;
	fixture.querySelector('p')!.click();
	await Promise.resolve();
	assert(true, 'logging network failure does not throw');
	window.fetch = (() => { throw new Error('logging synchronous failure'); }) as typeof fetch;
	fixture.querySelector('p')!.click();
	assert(true, 'logging synchronous failure does not throw');
	const getItem = Storage.prototype.getItem;
	window.fetch = ((url: string | URL | Request, options: RequestInit) => {
		requests.push({ url: String(url), body: JSON.parse(String(options.body)), options });
		return Promise.resolve(new Response(null, { status: 204 }));
	}) as typeof fetch;
	try {
		Storage.prototype.getItem = () => { throw new DOMException('blocked', 'SecurityError'); };
		fixture.querySelector('p')!.click();
		assert(latest().visitor_id === visitor && latest().session_id === session, 'blocked storage keeps in-memory identity and still sends');
	} finally { Storage.prototype.getItem = getItem; }
	fixture.querySelector('p')!.textContent = '   ';
	fixture.querySelector('p')!.click();
	assert(latest().target_label === 'p', 'whitespace-only elements still have a label');
	const beforeDispose = requests.length;
	dispose();
	fixture.querySelector('p')!.click();
	assert(requests.length === beforeDispose, 'listeners removed on layout teardown');
	result.textContent = `${checks} telemetry checks passed`;
	result.dataset.status = 'passed';
} catch (error) {
	result.textContent = error instanceof Error ? `${error.message}\n${error.stack}` : String(error);
	result.dataset.status = 'failed';
	throw error;
} finally {
	dispose();
	window.fetch = originalFetch;
	history.replaceState({}, '', originalPath);
	if (originalToken === null) localStorage.removeItem('local-field.access-token');
	else localStorage.setItem('local-field.access-token', originalToken);
	fixture.replaceChildren();
}
