import fs from 'node:fs';
import { rolldown } from 'rolldown';

const template = fs.readFileSync(new URL('./telemetry.test.html', import.meta.url), 'utf8');

for (const name of ['telemetry', 'api-latency', 'image-timing']) {
	const outputName = name === 'telemetry' ? 'audit' : name;
	const bundle = await rolldown({
		input: new URL(`./${name}.test.ts`, import.meta.url).pathname,
		plugins: [{
			name: 'latency-test-environment',
			resolveId(id) { if (id === '$app/environment' || id === '$lib/configs/constants') return '\0' + id; },
			load(id) {
				if (id === '\0$app/environment') return 'export const browser = true;';
				if (id === '\0$lib/configs/constants') return "export const SERVER_URL = 'http://api.example.test';";
			}
		}]
	});
	try {
		const generated = await bundle.generate({ format: 'esm' });
		const code = generated.output.find((item) => item.type === 'chunk').code;
		fs.writeFileSync(new URL(`../static/${outputName}-check.html`, import.meta.url), template.replace('<script type="module" src="./telemetry.test.ts"></script>', () => `<script type="module">${code}</script>`));
	} finally { await bundle.close(); }
	console.log(`Prepared ${outputName}-check.html; remove it after browser verification.`);
}
