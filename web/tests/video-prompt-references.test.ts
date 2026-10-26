import { buildVideoPromptReferences, type VideoPromptSource } from '../src/lib/utils/video-prompt-references.ts';

function equal(actual: unknown, expected: unknown) {
	if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
}

const first = { filename: 'first.png', fileId: 'first' };
const last = { filename: 'last.png', fileId: 'last' };
const stored = { filename: 'stored.png', fileId: 'stored' };
const device = { filename: 'device.png', file: new Blob(['image']) };
const selection = { mode: 'fl2v' as const, continuationMode: 'r2v' as const, segmentIndex: 0, first, last, images: [stored, device], videos: [{ filename: 'motion.mp4' }], audios: [{ filename: 'voice.wav' }] };
const previews: string[] = [];
async function preview(source: VideoPromptSource) { previews.push(source.filename); return `preview:${source.filename}`; }

let result = await buildVideoPromptReferences(selection, preview);
equal(result.map(({ kind, index, role }) => ({ kind, index, role })), [{ kind: 'image', index: 1, role: 'first_frame' }, { kind: 'image', index: 2, role: 'last_frame' }]);
equal(previews, ['first.png', 'last.png']);

result = await buildVideoPromptReferences({ ...selection, mode: 'r2v' }, preview);
equal(result.map(({ kind, index, filename }) => ({ kind, index, filename })), [
	{ kind: 'image', index: 1, filename: 'stored.png' }, { kind: 'image', index: 2, filename: 'device.png' },
	{ kind: 'video', index: 1, filename: 'motion.mp4' }, { kind: 'audio', index: 1, filename: 'voice.wav' }
]);
equal(result.slice(2).map((reference) => reference.image_data_url), [undefined, undefined]);

previews.length = 0;
result = await buildVideoPromptReferences({ ...selection, segmentIndex: 1 }, preview);
equal(result.map(({ kind, index, role }) => ({ kind, index, role })), [
	{ kind: 'image', index: 1, role: 'continuation_frame' }, { kind: 'image', index: 2, role: 'identity' }, { kind: 'image', index: 3, role: 'identity' }
]);
equal(result[0].image_data_url, undefined);
equal(previews, ['stored.png', 'device.png']);

previews.length = 0;
result = await buildVideoPromptReferences({ ...selection, segmentIndex: 1, continuationMode: 'i2v' }, preview);
equal(result.length, 1);
equal(result[0].role, 'continuation_frame');
equal(previews, []);

let failed = false;
try { await buildVideoPromptReferences(selection, async () => { throw new Error('Image decode failed'); }); } catch { failed = true; }
equal(failed, true);
console.log('Video prompt reference ordering, continuation, and preview error checks passed');
