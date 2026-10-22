import argparse
import importlib.machinery
import json
import os
from pathlib import Path
import sys
import types


def stage(name):
    print(f"LOCAL_FIELD_STAGE:{name}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--input')
    parser.add_argument('--output')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--temperature', type=float, default=1)
    parser.add_argument('--num-beams', type=int, default=10)
    args = parser.parse_args()
    os.chdir(args.repo)
    sys.path.insert(0, args.repo)
    os.environ['HF_HUB_OFFLINE'] = '1'
    import numpy as np
    import torch
    import torch.nn.functional as functional
    import trimesh
    from glb import load_mesh, export_rig
    from transformers import AutoModelForCausalLM

    def attention(q, k, v, **kwargs):
        output = functional.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2),
                                                       is_causal=kwargs.get('causal', False), enable_gqa=q.shape[2] != k.shape[2])
        return output.transpose(1, 2), None

    module = types.ModuleType('flash_attn_interface')
    module.__spec__ = importlib.machinery.ModuleSpec(module.__name__, loader=None)
    module.flash_attn_func = attention
    sys.modules[module.__name__] = module
    original = AutoModelForCausalLM.from_config

    def from_config(*positional, **kwargs):
        kwargs['attn_implementation'] = 'sdpa'
        return original(*positional, **kwargs)

    AutoModelForCausalLM.from_config = from_config
    from src.server.spec import get_model
    from src.data.transform import Transform
    from src.rig_package.info.asset import Asset

    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU를 사용할 수 없습니다.')
    if args.check:
        print(json.dumps({'ready': True, 'gpu': torch.cuda.get_device_name(0)}), flush=True)
        return
    if not args.input or not args.output:
        parser.error('--input and --output are required for inference')
    stage('loading_model')
    model = get_model('experiments/articulation_xl_quantization_256_token_4/grpo_1400.ckpt').eval()
    stage('preprocessing')
    gltf, parts, vertices, faces = load_mesh(args.input)
    blender_axes = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float32)
    mesh = trimesh.Trimesh(vertices=vertices @ blender_axes.T, faces=faces, process=False)
    asset = Asset(vertices=np.array(mesh.vertices, dtype=np.float32), faces=faces, vertex_normals=np.array(mesh.vertex_normals), face_normals=np.array(mesh.face_normals))
    transform = Transform.parse(**model.transform_config['predict_transform'])
    transform.apply(asset)
    if asset.vertices.shape != vertices.shape:
        raise RuntimeError('SkinTokens preprocessing changed the vertex count.')
    homogeneous = np.column_stack([vertices, np.ones(len(vertices))])
    affine, _, rank, _ = np.linalg.lstsq(homogeneous, asset.vertices, rcond=None)
    matrix = np.eye(4)
    matrix[:3] = affine.T
    if rank < 4 or not np.allclose(homogeneous @ affine, asset.vertices, atol=1e-4):
        raise ValueError('입체적인 GLB 메시가 필요합니다.')
    stage('rigging')
    with torch.inference_mode():
        result = model.generate(vertices=torch.from_numpy(asset.sampled_vertices).float().cuda(),
                                normals=torch.from_numpy(asset.sampled_normals).float().cuda(),
                                cls='articulation',
                                max_length=2048, top_k=5, top_p=0.95, temperature=args.temperature,
                                repetition_penalty=2., num_return_sequences=1, num_beams=args.num_beams, do_sample=True)
    rig = result.detokenize_output
    if rig is None or result.skin_pred is None:
        raise RuntimeError('SkinTokens가 리깅 결과를 반환하지 않았습니다.')
    stage('skinning')
    output = Asset.from_data(vertices=asset.vertices, faces=faces,
                             sampled_vertices=asset.sampled_vertices,
                             sampled_skin=result.skin_pred.float().cpu().numpy(),
                             joints=rig.joints, parents=np.array(rig.parents))
    joint_points = np.column_stack([output.joints, np.ones(output.J)]) @ np.linalg.inv(matrix).T
    stage('exporting')
    export_rig(gltf, parts, joint_points[:, :3], output.parents, output.skin, args.output, rig.joint_names)
    print(json.dumps({'joints': output.J, 'vertices': len(vertices)}), flush=True)


if __name__ == '__main__':
    main()
