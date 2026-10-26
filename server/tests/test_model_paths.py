import json
import unittest
from unittest.mock import patch

from app import comfyui, music, three_d
from model_fixtures import model_object_info


class ModelFolderTest(unittest.TestCase):
    def test_music_readiness_and_graph_follow_renamed_checkpoint(self):
        data = model_object_info()
        workflow = json.loads(music._WORKFLOW_PATH.read_text())
        data.update({node['class_type']: data.get(node['class_type'], {}) for node in workflow.values()})
        with patch.object(music, '_request_json', return_value=data):
            self.assertEqual(music._readiness(), [])
            graph, _ = music._build_prompt(music.MusicGenerationRequest(description='piano', seed=1))
        self.assertEqual(graph['1']['inputs']['ckpt_name'], 'YuE2/renamed.safetensors')
        data['CheckpointLoaderSimple']['input']['required']['ckpt_name'] = [['Other/renamed.safetensors']]
        with patch.object(music, '_request_json', return_value=data):
            self.assertTrue(music._readiness())
            with self.assertRaises(comfyui._ComfyUIError):
                music._build_prompt(music.MusicGenerationRequest(description='piano'))

    def test_three_d_readiness_and_graph_follow_all_five_renamed_models(self):
        data = model_object_info()
        workflow = json.loads(three_d._WORKFLOW_PATH.read_text())
        data.update({node['class_type']: data.get(node['class_type'], {}) for node in workflow.values()})
        request = three_d.ThreeDGenerationRequest(source={'file_index': 0}, seed=1)
        with patch.object(three_d, '_request_json', return_value=data):
            self.assertEqual(three_d._readiness(), ([], []))
            graph, _ = three_d._build_prompt(request, 'source.png')
        for node_id, key, expected in (
            ('2', 'bg_removal_name', 'TripoSplat/renamed.safetensors'),
            ('7', 'unet_name', 'TripoSplat/custom.safetensors'),
            ('8', 'clip_name', 'TripoSplat/renamed.safetensors'),
            ('9', 'vae_name', 'TripoSplat/Image/renamed.safetensors'),
            ('12', 'vae_name', 'TripoSplat/Splat/renamed.safetensors'),
        ):
            self.assertEqual(graph[node_id]['inputs'][key], expected)
        data['VAELoader']['input']['required']['vae_name'][0].remove('TripoSplat/Splat/renamed.safetensors')
        with patch.object(three_d, '_request_json', return_value=data):
            self.assertIn('VAELoader.vae_name: TripoSplat/Splat/', three_d._readiness()[1])
            with self.assertRaises(comfyui._ComfyUIError):
                three_d._build_prompt(request, 'source.png')

    def test_folder_resolution_ignores_prompt_text_and_rejects_sibling_prefix(self):
        data = {'CLIPLoader': {'input': {'required': {'clip_name': [['Qwen-other/renamed.safetensors', 'Qwen/Encoder/nested/z.safetensors', 'Qwen/Encoder/a.safetensors']]}}}}
        graph = {'1': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'folder://Qwen/Encoder/'}}, '2': {'class_type': 'TextGenerate', 'inputs': {'prompt': 'folder://literal-user-text/'}}}
        comfyui._resolve_model_inputs(graph, data)
        self.assertEqual(graph['1']['inputs']['clip_name'], 'Qwen/Encoder/a.safetensors')
        self.assertEqual(graph['2']['inputs']['prompt'], 'folder://literal-user-text/')
