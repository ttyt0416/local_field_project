import asyncio
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app import comfyui
from app.auth import UserResponse
from app.presets import PresetCreateRequest


class Qwen21WorkflowTest(unittest.TestCase):
    def request(self, **values):
        return comfyui.ImageToImageGenerationRequest(model_family="qwen_image_2_1", checkpoint=comfyui._EDIT_MODELS["qwen_image_2_1"]["checkpoint"], prompt="Replace the background", source={"file_index": 0}, seed=123, **{"prompt_enhancement_enabled": False, **values})

    def options(self):
        model = comfyui._EDIT_MODELS["qwen_image_2_1"]
        def node(**values):
            return {"input": {"required": {key: [choices] for key, choices in values.items()}}}
        data = {name: {} for name in model["nodes"]}
        data.update({"UNETLoader": node(unet_name=[model["checkpoint"], "qwen_image_2.1_bf16.safetensors"]), "CLIPLoader": node(clip_name=[model["text_encoder"]]), "VAELoader": node(vae_name=[model["vae"]]), "KSampler": node(sampler_name=["euler", "heun"], scheduler=["simple", "normal"])})
        with patch.object(comfyui, "_request_json", return_value=data):
            return comfyui._image_options("qwen_image_2_1")

    def test_turbo_defaults_and_options_exclude_base_checkpoint(self):
        request, options = self.request(), self.options()
        self.assertEqual((request.steps, request.cfg, request.denoise), (8, 1, 1))
        self.assertEqual(options.checkpoints, [request.checkpoint])
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

    def test_prompt_enhancer_reads_all_references_with_official_thinking_settings(self):
        request = self.request(prompt_enhancement_enabled=True)
        self.assertEqual(comfyui._effective_positive_prompt(request), request.prompt)
        graph, _ = comfyui._build_prompt(request, input_image="source.png", input_references=["style.png"])
        self.assertEqual(graph["12"]["inputs"]["prompt"], ["34", 0])
        self.assertEqual(graph["34"]["inputs"]["on_true"], request.prompt)
        self.assertEqual(graph["34"]["inputs"]["on_false"], ["31", 0])
        self.assertEqual(graph["33"]["inputs"]["string_b"], "")
        self.assertEqual(graph["31"]["class_type"], "TextGenerate")
        self.assertEqual(graph["30"]["inputs"]["clip_name"], comfyui._QWEN21_PROMPT_ENHANCER)
        self.assertTrue(graph["31"]["inputs"]["thinking"])
        self.assertEqual(graph["31"]["inputs"]["max_length"], 4096)
        self.assertEqual(graph["31"]["inputs"]["sampling_mode.top_k"], 20)
        self.assertEqual(graph["32"]["inputs"], {"images.image0": ["201", 0], "images.image1": ["202", 0]})
        self.assertEqual(graph["201"]["inputs"]["image"], ["11", 0])
        self.assertEqual(graph["202"]["inputs"]["image"], graph["12"]["inputs"]["images.image_2"])
        with self.assertRaises(HTTPException) as caught:
            comfyui._validate_model_choice(request, self.options())
        self.assertEqual(caught.exception.status_code, 503)

    def test_edit_requires_source_and_has_i2i_preset_namespace(self):
        with self.assertRaises(HTTPException):
            comfyui._build_prompt(self.request())
        preset = PresetCreateRequest(type="i2i_qwen_image_2_1", name="turbo", values={"steps": 8, "cfg": 1, "scheduler": comfyui._QWEN21_TURBO_SCHEDULER})
        self.assertEqual(preset.values.steps, 8)
