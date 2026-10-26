import fs from 'node:fs';
import ts from 'typescript';
import { rolldown } from 'rolldown';

const options = { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 };
const compile = (source) => ts.transpileModule(source, { compilerOptions: options }).outputText;
const utility = compile(fs.readFileSync(new URL('../src/lib/utils/telemetry.ts', import.meta.url), 'utf8')
	.replace(/^import .*$/m, "const SERVER_URL = 'http://api.example.test';")).replace(/^export /gm, '');
const tests = compile(fs.readFileSync(new URL('./telemetry.test.ts', import.meta.url), 'utf8')
	.replace(/^import .*$/m, '')).replace(/^export \{\};?$/gm, '');
const template = fs.readFileSync(new URL('./telemetry.test.html', import.meta.url), 'utf8');
const output = new URL('../static/audit-check.html', import.meta.url);
fs.writeFileSync(output, template.replace('<script type="module" src="./telemetry.test.ts"></script>', () => `<script type="module">${utility}\n${tests}</script>`));
console.log(`Prepared ${output.pathname}; remove this generated file after browser verification.`);

const bundle = await rolldown({
	input: new URL('./api-latency.test.ts', import.meta.url).pathname,
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
	fs.writeFileSync(new URL('../static/api-latency-check.html', import.meta.url), template.replace('<script type="module" src="./telemetry.test.ts"></script>', () => `<script type="module">${code}</script>`));
} finally { await bundle.close(); }
console.log('Prepared api-latency-check.html; remove it after browser verification.');
