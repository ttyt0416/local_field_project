from copy import deepcopy
from pathlib import Path

import numpy as np
from pygltflib import Accessor, BufferView, GLTF2, Node, Skin
from scipy.spatial.transform import Rotation


def read_accessor(gltf, index):
    accessor = gltf.accessors[index]
    if accessor.sparse or accessor.bufferView is None:
        raise ValueError("Sparse GLB accessors are not supported.")
    view = gltf.bufferViews[accessor.bufferView]
    if view.buffer != 0:
        raise ValueError("Only self-contained GLB files are supported.")
    dtype = {5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}[accessor.componentType]
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[accessor.type]
    item = np.dtype(dtype).itemsize
    return np.ndarray((accessor.count, width), dtype=dtype, buffer=gltf.binary_blob(),
                      offset=(view.byteOffset or 0) + (accessor.byteOffset or 0),
                      strides=(view.byteStride or item * width, item)).copy()


def load_mesh(path):
    gltf = GLTF2().load_binary(str(path))
    if any(buffer.uri for buffer in gltf.buffers) or any(image.uri and not image.uri.startswith('data:') for image in gltf.images):
        raise ValueError("외부 파일을 참조하는 GLB는 지원하지 않습니다.")
    if gltf.extensionsRequired:
        raise ValueError("압축 등 필수 확장이 없는 GLB를 사용해 주세요.")
    parts, vertices, faces = [], [], []
    visited = set()

    def visit(index, parent):
        if index in visited:
            raise ValueError("GLB node hierarchy contains a cycle or shared node.")
        visited.add(index)
        node = gltf.nodes[index]
        if node.skin is not None or getattr(node, 'weights', None):
            raise ValueError("이미 리깅되었거나 변형된 GLB 대신 원본 메시를 사용해 주세요.")
        if node.matrix:
            local = np.array(node.matrix).reshape(4, 4).T
        else:
            local = np.eye(4)
            local[:3, :3] = Rotation.from_quat(node.rotation or [0, 0, 0, 1]).as_matrix() @ np.diag(node.scale or [1, 1, 1])
            local[:3, 3] = node.translation or [0, 0, 0]
        world = parent @ local
        if node.mesh is not None:
            mesh = deepcopy(gltf.meshes[node.mesh])
            node.mesh = len(gltf.meshes)
            gltf.meshes.append(mesh)
            for primitive in mesh.primitives:
                if primitive.mode not in (None, 4) or primitive.targets:
                    raise ValueError("삼각형 메시이며 morph target이 없는 GLB가 필요합니다.")
                positions = read_accessor(gltf, primitive.attributes.POSITION)
                points = positions @ world[:3, :3].T + world[:3, 3]
                start = sum(len(v) for v in vertices)
                triangles = read_accessor(gltf, primitive.indices).reshape(-1, 3) if primitive.indices is not None else np.arange(len(points)).reshape(-1, 3)
                if len(points) == 0 or np.max(triangles) >= len(points):
                    raise ValueError("GLB mesh has invalid indices.")
                parts.append((index, primitive, world, start, len(points)))
                vertices.append(points)
                faces.append(triangles + start)
        for child in node.children or []:
            visit(child, world)

    scene = gltf.scenes[gltf.scene or 0]
    for root in scene.nodes:
        visit(root, np.eye(4))
    if not vertices:
        raise ValueError("GLB에서 메시를 찾을 수 없습니다.")
    points, triangles = np.concatenate(vertices).astype(np.float32), np.concatenate(faces)
    if len(points) > 1_000_000 or len(triangles) > 2_000_000 or not np.isfinite(points).all():
        raise ValueError("GLB 메시가 너무 크거나 올바르지 않습니다.")
    return gltf, parts, points, triangles


def export_rig(gltf, parts, joints, parents, weights, output, names=None):
    joints = np.asarray(joints, dtype=np.float32)
    parents = np.asarray(parents, dtype=int)
    weights = np.asarray(weights, dtype=np.float32)
    count = len(joints)
    if count == 0 or count > 65535 or weights.shape[1] != count or not np.isfinite(joints).all() or not np.isfinite(weights).all():
        raise ValueError("SkinTokens가 올바르지 않은 리깅 결과를 반환했습니다.")
    if len(parents) != count or np.any(parents >= count) or np.any(parents < -1):
        raise ValueError("Invalid skeleton hierarchy.")
    for index in range(count):
        chain = set()
        current = index
        while current != -1:
            if current in chain:
                raise ValueError("Skeleton hierarchy contains a cycle.")
            chain.add(current)
            current = int(parents[current])
    blob = bytearray(gltf.binary_blob())

    def append(array, kind, component):
        array = np.ascontiguousarray(array)
        blob.extend(b'\0' * (-len(blob) % 4))
        offset = len(blob)
        blob.extend(array.tobytes())
        view = len(gltf.bufferViews)
        gltf.bufferViews.append(BufferView(buffer=0, byteOffset=offset, byteLength=array.nbytes))
        index = len(gltf.accessors)
        gltf.accessors.append(Accessor(bufferView=view, componentType=component, count=len(array), type=kind))
        return index

    offset = len(gltf.nodes)
    roots = []
    for index, parent in enumerate(parents):
        delta = joints[index] - joints[parent] if parent >= 0 else joints[index]
        children = (np.flatnonzero(parents == index) + offset).tolist()
        gltf.nodes.append(Node(name=(names[index] if names else f"bone_{index}"), translation=delta.tolist(), children=children))
        if parent < 0:
            roots.append(offset + index)
    gltf.scenes[gltf.scene or 0].nodes.extend(roots)
    inverse = np.tile(np.eye(4), (count, 1, 1))
    inverse[:, :3, 3] = -joints
    skins = {}
    for node_index, primitive, world, start, length in parts:
        skin = np.maximum(weights[start:start + length], 0)
        top = np.argsort(skin, axis=1)[:, -min(4, count):]
        values = np.take_along_axis(skin, top, axis=1)
        empty = values.sum(axis=1) <= 1e-12
        values[empty, -1] = 1
        values /= values.sum(axis=1, keepdims=True)
        pad = 4 - top.shape[1]
        primitive.attributes.JOINTS_0 = append(np.pad(top, ((0, 0), (0, pad))).astype('<u2'), 'VEC4', 5123)
        primitive.attributes.WEIGHTS_0 = append(np.pad(values, ((0, 0), (0, pad))).astype('<f4'), 'VEC4', 5126)
        if node_index not in skins:
            matrices = (inverse @ world).transpose(0, 2, 1).reshape(count, 16).astype('<f4')
            accessor = append(matrices, 'MAT4', 5126)
            skins[node_index] = len(gltf.skins)
            gltf.skins.append(Skin(inverseBindMatrices=accessor, joints=list(range(offset, offset + count)), name="SkinTokens"))
        gltf.nodes[node_index].skin = skins[node_index]
    gltf.animations = []
    gltf.buffers[0].byteLength = len(blob)
    gltf.set_binary_blob(bytes(blob))
    gltf.save_binary(str(Path(output)))
