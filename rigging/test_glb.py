from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import numpy as np
from pygltflib import GLTF2, Node
import trimesh

from glb import export_rig, load_mesh, read_accessor


class GLBRigTest(unittest.TestCase):
    def test_preserves_transformed_instances_materials_and_bind_pose(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / 'source.glb', Path(temporary) / 'target.glb'
            scene = trimesh.Scene()
            mesh = trimesh.creation.box()
            mesh.visual.vertex_colors = [220, 50, 80, 255]
            scene.add_geometry(mesh)
            scene.export(str(source))
            document = GLTF2().load_binary(str(source))
            node_index = next(i for i, node in enumerate(document.nodes) if node.mesh is not None)
            node = document.nodes[node_index]
            node.translation = [2, 3, 4]
            node.rotation = [0, 0, np.sin(.25), np.cos(.25)]
            node.scale = [2, 1, 3]
            instance = deepcopy(node)
            instance.translation = [-2, 1, 4]
            document.nodes.append(instance)
            document.scenes[document.scene or 0].nodes.append(len(document.nodes) - 1)
            document.save_binary(str(source))
            original, parts, points, _ = load_mesh(source)
            materials = deepcopy(original.materials)
            joints = np.array([[0, 0, 0], [0, 1, 0]], dtype=np.float32)
            weights = np.tile([.25, .75], (len(points), 1))
            export_rig(original, parts, joints, [-1, 0], weights, target)
            output = GLTF2().load_binary(str(target))
            self.assertEqual(materials, output.materials)
            self.assertEqual(len(output.skins), 2)
            for node_index, primitive, world, start, length in parts:
                skin = output.skins[output.nodes[node_index].skin]
                w = read_accessor(output, primitive.attributes.WEIGHTS_0)
                ids = read_accessor(output, primitive.attributes.JOINTS_0)
                self.assertTrue(np.allclose(w.sum(axis=1), 1))
                self.assertTrue((ids < 2).all())
                matrices = read_accessor(output, skin.inverseBindMatrices).reshape(-1, 4, 4).transpose(0, 2, 1)
                for index in range(2):
                    joint_world = np.eye(4)
                    joint_world[:3, 3] = joints[index]
                    self.assertTrue(np.allclose(np.linalg.inv(world) @ joint_world @ matrices[index], np.eye(4), atol=1e-6))
                self.assertIsNotNone(primitive.attributes.COLOR_0)

    def test_rejects_existing_skins_instead_of_corrupting_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'model.glb'
            trimesh.creation.box().export(str(source))
            document = GLTF2().load_binary(str(source))
            next(node for node in document.nodes if node.mesh is not None).skin = 0
            document.save_binary(str(source))
            with self.assertRaisesRegex(ValueError, '리깅'):
                load_mesh(source)

    def test_rejects_cyclic_skeleton(self):
        with self.assertRaisesRegex(ValueError, 'cycle'):
            export_rig(GLTF2(), [], np.zeros((2, 3)), [1, 0], np.ones((1, 2)), '/tmp/unused.glb')


if __name__ == '__main__':
    unittest.main()
