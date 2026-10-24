import { inspectRig } from '../src/lib/utils/rig-inspection.ts';

const cases: { name: string; run: () => Promise<void> }[] = [];
function test(name: string, run: () => Promise<void>) {
	cases.push({ name, run });
}
const assert = {
	equal(actual: unknown, expected: unknown) {
		if (actual !== expected) throw new Error(`${actual} !== ${expected}`);
	},
	deepEqual(actual: unknown, expected: unknown) {
		this.equal(JSON.stringify(actual), JSON.stringify(expected));
	},
	ok(value: boolean) {
		if (!value) throw new Error('Assertion failed');
	},
	async rejects(promise: Promise<unknown>) {
		try { await promise; } catch { return; }
		throw new Error('Expected rejection');
	}
};

function glb(document: object): Blob {
	const json = new TextEncoder().encode(JSON.stringify(document));
	const length = Math.ceil(json.length / 4) * 4;
	const buffer = new ArrayBuffer(20 + length);
	const view = new DataView(buffer);
	[0x46546c67, 2, buffer.byteLength, length, 0x4e4f534a].forEach((value, i) => view.setUint32(i * 4, value, true));
	const data = new Uint8Array(buffer, 20);
	data.fill(32);
	data.set(json);
	return new Blob([buffer]);
}

const mesh = { primitives: [{ attributes: { JOINTS_0: 0, WEIGHTS_0: 1 } }] };

test('combines parent rotation, scale and translation and connects through non-joint nodes', async () => {
	const result = await inspectRig(glb({
		nodes: [
			{ name: 'root', children: [1], translation: [2, 3, 4], rotation: [0, 0, Math.SQRT1_2, Math.SQRT1_2], scale: [2, 2, 2] },
			{ translation: [1, 0, 0], children: [2] },
			{ name: 'tip', translation: [1, 0, 0] },
			{ mesh: 0, skin: 0 }
		],
		scenes: [{ nodes: [0, 3] }], skins: [{ joints: [0, 2] }], meshes: [mesh]
	}));
	assert.equal(result.skinnedMeshes, 1);
	assert.equal(result.animations, 0);
	assert.equal(result.joints[1].parent, 0);
	assert.deepEqual(result.joints[0].position, [2, 3, 4]);
	result.joints[1].position.forEach((value, i) => assert.ok(Math.abs(value - [2, 7, 4][i]) < 1e-10));
});

test('uses matrix transforms and excludes unused skins and meshes', async () => {
	const result = await inspectRig(glb({
		nodes: [{ name: 'joint', matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 6, 7, 1] }, { mesh: 0, skin: 0 }, { mesh: 0, skin: 1 }],
		scenes: [{ nodes: [0, 1] }], skins: [{ joints: [0] }, { joints: [0, 2] }], meshes: [mesh], animations: [{}]
	}));
	assert.equal(result.skinnedMeshes, 1);
	assert.equal(result.joints.length, 1);
	assert.deepEqual(result.joints[0].position, [5, 6, 7]);
	assert.equal(result.animations, 1);
});

test('ordinary mesh has no rig', async () => {
	const result = await inspectRig(glb({ nodes: [{ mesh: 0 }], meshes: [{ primitives: [{ attributes: { POSITION: 0 } }] }] }));
	assert.deepEqual(result, { joints: [], skinnedMeshes: 0, animations: 0 });
});

test('rejects truncated files and cyclic joint transforms', async () => {
	await assert.rejects(inspectRig(new Blob(['glTF'])));
	await assert.rejects(inspectRig(glb({ nodes: [{ children: [0], mesh: 0, skin: 0 }], scenes: [{ nodes: [0] }], skins: [{ joints: [0] }], meshes: [mesh] })));
});

for (const item of cases) {
	await item.run();
	console.log(`PASS: ${item.name}`);
}
