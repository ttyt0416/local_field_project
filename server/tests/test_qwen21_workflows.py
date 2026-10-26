import asyncio
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from model_fixtures import model_object_info

from app import comfyui
from app.auth import UserResponse
from app.presets import PresetCreateRequest


class Qwen21WorkflowTest(unittest.TestCase):
    def setUp(self):
        request = patch.object(comfyui, "_request_json", return_value=model_object_info())
        request.start()
        self.addCleanup(request.stop)

    def request(self, **values):
        return comfyui.ImageToImageGenerationRequest(model_family="qwen_image_2_1", checkpoint="Qwen/custom.safetensors", prompt="Replace the background", source={"file_index": 0}, seed=123, **{"prompt_enhancement_enabled": False, **values})

    def options(self):
        model = comfyui._EDIT_MODELS["qwen_image_2_1"]
        def node(**values):
            return {"input": {"required": {key: [choices] for key, choices in values.items()}}}
        data = {**model_object_info(), **{name: {} for name in model["nodes"]}}
        data.update({"UNETLoader": node(unet_name=["Qwen/custom.safetensors", "Qwen/nested/renamed.safetensors", "Qwen-other/ignored.safetensors", "qwen_image_2.1_bf16.safetensors"]), "CLIPLoader": node(clip_name=["Qwen/Encoder/renamed.safetensors"]), "VAELoader": node(vae_name=["Qwen/renamed.safetensors"]), "KSampler": node(sampler_name=["euler", "heun"], scheduler=["simple", "normal"])})
        with patch.object(comfyui, "_request_json", return_value=data):
            return comfyui._image_options("qwen_image_2_1")

    def test_turbo_defaults_and_options_accept_all_qwen_folder_names(self):
        request, options = self.request(), self.options()
        self.assertEqual((request.steps, request.cfg, request.denoise), (8, 1, 1))
        self.assertEqual(options.checkpoints, [request.checkpoint, "Qwen/nested/renamed.safetensors"])
        self.assertEqual(options.default_steps, 8)
        self.assertEqual(options.samplers, ["euler"])
        self.assertEqual(options.schedulers, [comfyui._QWEN21_TURBO_SCHEDULER])
        comfyui._validate_model_choice(request, options)

    def test_single_image_uses_native_encoder_output_canvas_and_official_sigmas(self):
        graph, seed = comfyui._build_prompt(self.request(width=768, height=1024), input_image="source.png")
        self.assertEqual(seed, 123)
        self.assertEqual(graph["12"]["class_type"], "TextEncodeQwenImage21")
        self.assertEqual(graph["12"]["inputs"]["resolution"], 0)
        self.assertEqual(graph["12"]["inputs"]["images.image_1"], ["11", 0])
        self.assertEqual(graph["11"]["inputs"]["width"], 768)
        self.assertEqual(graph["8"]["inputs"]["latent_image"], ["12", 2])
        self.assertEqual(graph["8"]["class_type"], "SamplerCustomAdvanced")
        self.assertEqual(graph["17"]["inputs"]["cfg"], 1)
        sigmas = [float(value) for value in graph["14"]["inputs"]["sigmas"].split(",")]
        self.assertEqual(sigmas, [1, .978453, .95418, .926626, .89508, .845148, .704534, .414568, 0])
        self.assertEqual(graph["9"]["inputs"]["samples"], ["8", 0])

    def test_multi_reference_order_is_preserved_for_all_ten_images(self):
        refs = [f"reference-{i}.png" for i in range(2, 11)]
        request = self.request(references=[{"file_index": i} for i in range(1, 10)])
        comfyui._validate_image_sources(request, [None] * 10)
        graph, _ = comfyui._build_prompt(request, input_image="source.png", input_references=refs)
        for index, filename in enumerate(refs, start=2):
            scale_id = graph["12"]["inputs"][f"images.image_{index}"][0]
            load_id = graph[scale_id]["inputs"]["image"][0]
            self.assertEqual(graph[load_id]["inputs"]["image"], filename)
            self.assertEqual(graph[scale_id]["inputs"]["resolution_steps"], 32)
        self.assertTrue(graph["10"]["inputs"]["filename_prefix"].endswith("R2I"))
        with self.assertRaises(ValidationError):
            self.request(references=[{"file_index": i} for i in range(10)])

    def test_incompatible_sampling_is_rejected_before_source_resolution(self):
        for values in ({"steps": 7}, {"cfg": 3}, {"sampler_name": "heun"}, {"scheduler": "simple"}, {"denoise": .5}, {"width": 520}):
            with self.subTest(values=values), self.assertRaises(HTTPException):
                comfyui._validate_model_choice(self.request(**values), self.options())
        request = self.request(steps=4)
        user = UserResponse(id=uuid4(), username="tester", created_at="2026-10-18T00:00:00Z")
        with patch.object(comfyui, "_image_options", return_value=self.options()), patch.object(comfyui, "_resolve_image_source") as resolve:
            with self.assertRaises(HTTPException):
                asyncio.run(comfyui.create_image_to_image_generation(request.model_dump_json(), [], user))
            resolve.assert_not_called()

    def test_vllm_improved_prose_reaches_encoder_without_local_llm_nodes(self):
        request = self.request(prompt_enhancement_enabled=True, improved_prompt="배경만 파란색으로 바꾸고 인물은 유지하세요.", positive_prompt_prefix="Keep the composition")
        graph, _ = comfyui._build_prompt(request, input_image="source.png", input_references=["style.png"])
        self.assertEqual(graph["12"]["inputs"]["prompt"], "Keep the composition, 배경만 파란색으로 바꾸고 인물은 유지하세요.")
        self.assertEqual(graph["12"]["inputs"]["images.image_1"], ["11", 0])
        self.assertIn("images.image_2", graph["12"]["inputs"])
        self.assertNotIn("TextGenerate", {node["class_type"] for node in graph.values()})
        options = self.options()
        self.assertTrue(options.prompt_enhancer_available)
        comfyui._validate_model_choice(request, options)

    def test_enabled_enhancement_requires_improved_prose(self):
        with self.assertRaises(HTTPException) as caught:
            comfyui._build_prompt(self.request(prompt_enhancement_enabled=True), input_image="source.png")
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("개선된 프롬프트", caught.exception.detail)

    def test_missing_improvement_is_rejected_before_source_resolution(self):
        request = self.request(prompt_enhancement_enabled=True)
        with patch.object(comfyui, "_image_options", return_value=self.options()), patch.object(comfyui, "_resolve_image_source") as resolve:
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(comfyui.create_image_to_image_generation(request.model_dump_json(), [], UserResponse(id=uuid4(), username="tester")))
        self.assertEqual(caught.exception.status_code, 422)
        resolve.assert_not_called()

    def test_edit_requires_source_and_has_i2i_preset_namespace(self):
        with self.assertRaises(HTTPException):
            comfyui._build_prompt(self.request())
        preset = PresetCreateRequest(type="i2i_qwen_image_2_1", name="turbo", values={"steps": 8, "cfg": 1, "scheduler": comfyui._QWEN21_TURBO_SCHEDULER})
        self.assertEqual(preset.values.steps, 8)
