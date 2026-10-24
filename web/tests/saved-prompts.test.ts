import { appendPrompt } from '../src/lib/utils/saved-prompts.ts';

const assert = {
	equal(actual: unknown, expected: unknown) { if (actual !== expected) throw new Error(`Expected ${String(expected)}, received ${String(actual)}`); },
	throws(run: () => unknown, pattern: RegExp) {
		try { run(); } catch (error) { if (error instanceof Error && pattern.test(error.message)) return; throw error; }
		throw new Error('Expected an error');
	}
};

assert.equal(appendPrompt('existing prompt', 'saved prompt', 'image'), 'existing prompt, saved prompt');
assert.equal(appendPrompt('existing prompt, ', 'saved prompt', 'image'), 'existing prompt, saved prompt');
assert.equal(appendPrompt('existing prompt,', 'saved prompt', 'image'), 'existing prompt, saved prompt');
assert.equal(appendPrompt('first line\nsecond line', 'saved prompt', 'video'), 'first line\nsecond line\nsaved prompt');
assert.equal(appendPrompt('original  ', 'addition', 'image'), 'original  addition');
assert.equal(appendPrompt('', 'saved prompt', 'video'), 'saved prompt');
assert.equal(appendPrompt('original', '  ', 'image'), 'original');
assert.equal(appendPrompt('x'.repeat(4997), 'y', 'image').length, 5000);
assert.throws(() => appendPrompt('x'.repeat(4998), 'y', 'image'), /5,000/);
console.log('9 saved-prompt append checks passed');
