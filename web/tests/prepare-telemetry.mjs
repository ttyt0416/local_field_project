import fs from 'node:fs';
import ts from 'typescript';

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
