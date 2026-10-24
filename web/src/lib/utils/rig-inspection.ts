export type RigJoint = {
	id: number;
	name: string;
	parent: number | null;
	position: [number, number, number];
};

export type RigInspection = {
	joints: RigJoint[];
	skinnedMeshes: number;
	animations: number;
};

type Node = {
	name?: string;
	children?: number[];
	matrix?: number[];
	translation?: number[];
	rotation?: number[];
	scale?: number[];
	mesh?: number;
	skin?: number;
};

type Document = {
	nodes?: Node[];
	skins?: { joints: number[] }[];
	meshes?: { primitives: { attributes: Record<string, number> }[] }[];
	scenes?: { nodes: number[] }[];
	scene?: number;
	animations?: unknown[];
};

function localMatrix(node: Node): number[] {
	if (node.matrix) return node.matrix;
	const [x, y, z, w] = node.rotation ?? [0, 0, 0, 1];
	const [sx, sy, sz] = node.scale ?? [1, 1, 1];
	const [tx, ty, tz] = node.translation ?? [0, 0, 0];
	return [
		(1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + z * w) * sx, 2 * (x * z - y * w) * sx, 0,
		2 * (x * y - z * w) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + x * w) * sy, 0,
		2 * (x * z + y * w) * sz, 2 * (y * z - x * w) * sz, (1 - 2 * (x * x + y * y)) * sz, 0,
		tx, ty, tz, 1
	];
}

function multiply(a: number[], b: number[]): number[] {
	return Array.from({ length: 16 }, (_, index) => {
		const column = Math.floor(index / 4);
		const row = index % 4;
		return a[row] * b[column * 4] + a[4 + row] * b[column * 4 + 1]
			+ a[8 + row] * b[column * 4 + 2] + a[12 + row] * b[column * 4 + 3];
	});
}

export async function inspectRig(blob: Blob): Promise<RigInspection> {
	const header = new DataView(await blob.slice(0, 20).arrayBuffer());
	if (header.byteLength < 20 || header.getUint32(0, true) !== 0x46546c67
		|| header.getUint32(4, true) !== 2 || header.getUint32(8, true) !== blob.size
		|| header.getUint32(16, true) !== 0x4e4f534a) {
		throw new Error('GLB 2.0 파일의 뼈대 정보를 읽을 수 없습니다.');
	}
	const jsonLength = header.getUint32(12, true);
	if (20 + jsonLength > blob.size) throw new Error('GLB JSON 데이터가 올바르지 않습니다.');
	const document: Document = JSON.parse(await blob.slice(20, 20 + jsonLength).text());
	const nodes = document.nodes ?? [];
	const parents = new Map<number, number>();
	nodes.forEach((node, index) => node.children?.forEach((child) => parents.set(child, index)));
	const active = new Set<number>();
	function visit(index: number) {
		if (active.has(index)) return;
		if (!nodes[index]) throw new Error('GLB 관절 계층이 올바르지 않습니다.');
		active.add(index);
		nodes[index].children?.forEach(visit);
	}
	const roots = document.scenes?.[document.scene ?? 0]?.nodes ?? nodes.map((_, i) => i).filter((i) => !parents.has(i));
	roots.forEach(visit);
	const skins = new Set<number>();
	let skinnedMeshes = 0;
	for (const index of active) {
		const node = nodes[index];
		if (node.skin === undefined || node.mesh === undefined) continue;
		if (!document.skins?.[node.skin]) continue;
		skins.add(node.skin);
		const primitives = document.meshes?.[node.mesh]?.primitives ?? [];
		if (primitives.some(({ attributes }) => attributes.JOINTS_0 !== undefined && attributes.WEIGHTS_0 !== undefined)) skinnedMeshes++;
	}
	const jointIds = new Set([...skins].flatMap((skin) => document.skins![skin].joints));
	const matrices = new Map<number, number[]>();
	const visiting = new Set<number>();
	function worldMatrix(index: number): number[] {
		const cached = matrices.get(index);
		if (cached) return cached;
		if (!nodes[index] || visiting.has(index)) throw new Error('GLB 관절 계층이 올바르지 않습니다.');
		visiting.add(index);
		const local = localMatrix(nodes[index]);
		const parent = parents.get(index);
		const world = parent === undefined ? local : multiply(worldMatrix(parent), local);
		if (world.length !== 16 || !world.every(Number.isFinite)) throw new Error('GLB 관절 좌표가 올바르지 않습니다.');
		matrices.set(index, world);
		visiting.delete(index);
		return world;
	}
	const joints = [...jointIds].map((id): RigJoint => {
		const world = worldMatrix(id);
		let parent = parents.get(id);
		const seen = new Set([id]);
		while (parent !== undefined && !jointIds.has(parent)) {
			if (seen.has(parent)) throw new Error('GLB 관절 계층이 올바르지 않습니다.');
			seen.add(parent);
			parent = parents.get(parent);
		}
		return { id, name: nodes[id].name || `관절 ${id + 1}`, parent: parent ?? null, position: [world[12], world[13], world[14]] };
	});
	return { joints, skinnedMeshes, animations: document.animations?.length ?? 0 };
}
