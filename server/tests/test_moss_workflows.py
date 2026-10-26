import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from model_fixtures import model_object_info

from app import comfyui
from app.moss import MossSettings, layout_prompt
from app.presets import PresetCreateRequest


class MossWorkflowTest(unittest.TestCase):
    def setUp(self):
        request = patch.object(comfyui, "_request_json", return_value=model_object_info())
        request.start()
        self.addCleanup(request.stop)

    def request(self, **values):
        return comfyui.ImageGenerationRequest(model_family="moss", checkpoint="MOSS/custom.safetensors", prompt="a poster", seed=123, **values)

    def test_layout_preserves_text_and_scales_non_square_coordinates(self):
        settings = MossSettings(layout_enabled=True, elements=[{"kind": "text", "caption": "heading", "text": "Hello\nWorld", "x": 0.25, "y": 0.1, "width": 0.5, "height": 0.2}])
        result = json.loads(layout_prompt("scene", settings, 1024, 512))
        self.assertEqual(result["items"][0]["bbox"], [-205, -256, -102, 256])
        self.assertEqual(result["items"][0]["text"], "Hello\nWorld")
        self.assertEqual(result["bbox_format"], "yxyx")
        with self.assertRaises(ValidationError):
            MossSettings(elements=[{"caption": "outside", "x": 0.8, "y": 0, "width": 0.5, "height": 0.5}])

    def test_sft_uses_moss_encoder_flux2_latents_and_selected_dmd(self):
        request = self.request(loras=[comfyui.LoraSelection(name="MOSS/arbitrary.safetensors", strength=0.7)], cfg=1, steps=8)
        graph, _ = comfyui._build_prompt(request)
        self.assertEqual(graph["3"]["inputs"]["type"], "moss_image")
        self.assertEqual(graph["7"]["class_type"], "EmptyFlux2LatentImage")
        self.assertEqual(graph["13"]["inputs"]["model"], ["20", 0])
        self.assertEqual(graph["20"]["inputs"]["strength_model"], 0.7)
        self.assertEqual(graph["8"]["inputs"]["latent_image"], ["7", 0])
        self.assertNotIn("14", graph)

    def test_t2i_layout_uses_text_conditioning_without_reference_nodes(self):
        settings = MossSettings(layout_enabled=True, elements=[{"kind": "text", "text": "HELLO", "x": 0, "y": 0, "width": 0.5, "height": 0.5}])
        graph, _ = comfyui._build_prompt(self.request(moss=settings))
        self.assertEqual(json.loads(graph["5"]["inputs"]["text"])["items"][0]["text"], "HELLO")
        self.assertEqual(graph["8"]["inputs"]["latent_image"], ["7", 0])
        self.assertEqual(graph["8"]["inputs"]["denoise"], 1)
        self.assertEqual(graph["14"]["class_type"], "SkipLayerGuidanceDiTSimple")
        self.assertFalse({"LoadImage", "ReferenceLatent", "UC_MOSSImageEditPatcher"} & {node["class_type"] for node in graph.values()})

    def test_improved_anima_style_prompt_preserves_moss_layout_text(self):
        settings = MossSettings(layout_enabled=True, elements=[{"kind": "text", "text": "HELLO", "x": 0, "y": 0, "width": 0.5, "height": 0.5}])
        graph, _ = comfyui._build_prompt(self.request(moss=settings, prompt_enhancement_enabled=True, improved_prompt="poster, soft studio lighting"))
        text = json.loads(graph["5"]["inputs"]["text"])
        self.assertEqual(text["summary"]["caption"], "poster, soft studio lighting")
        self.assertEqual(text["items"][0]["text"], "HELLO")

    def test_t2i_options_work_without_external_reference_package(self):
        def node(**inputs):
            return {"input": {"required": {key: [values] for key, values in inputs.items()}}}
        data = {
            "UNETLoader": node(unet_name=["MOSS/custom.safetensors", "MOSS/miaomiaoHaremMOSS_baseV10_3316573.safetensors", "MOSS/custom/model.safetensors", "Anima/a.safetensors", "moss_image_sft_bf16.safetensors", "MOSS-other/model.safetensors"]),
            "CLIPLoader": node(clip_name=["MOSS/renamed.safetensors"], type=["moss_image"]),
            "VAELoader": node(vae_name=["MOSS/renamed.safetensors"]),
            "LoraLoaderModelOnly": node(lora_name=["MOSS/arbitrary.safetensors", "Anima/a.safetensors"]),
            "KSampler": node(sampler_name=["euler"], scheduler=["sgm_uniform"]),
            "EmptyFlux2LatentImage": {},
        }
        with patch.object(comfyui, "_request_json", return_value=data):
            options = comfyui._image_options("moss")
        self.assertEqual(options.checkpoints, sorted(["MOSS/custom.safetensors", "MOSS/miaomiaoHaremMOSS_baseV10_3316573.safetensors", "MOSS/custom/model.safetensors"]))
        self.assertEqual(options.default_checkpoint, options.checkpoints[0])
        self.assertEqual(options.loras, ["MOSS/arbitrary.safetensors"])
        comfyui._validate_model_choice(self.request(), options)
        for checkpoint in options.checkpoints:
            request = self.request().model_copy(update={"checkpoint": checkpoint})
            comfyui._validate_model_choice(request, options)
            graph, _ = comfyui._build_prompt(request)
            self.assertEqual(graph["1"]["inputs"]["unet_name"], checkpoint)

    def test_moss_i2i_and_reference_inputs_are_rejected(self):
        with self.assertRaises(ValidationError):
            comfyui.ImageToImageGenerationRequest(**self.request().model_dump(), source={"file_index": 0})
        for kwargs in ({"input_image": "source.png"}, {"input_references": ["reference.png"]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(HTTPException) as caught:
                comfyui._build_prompt(self.request(), **kwargs)
            self.assertEqual(caught.exception.status_code, 422)
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(comfyui.create_image_to_image_generation(json.dumps({**self.request().model_dump(), "source": {"file_index": 0}}), [], None))
        self.assertEqual(caught.exception.status_code, 422)
        json.dumps(caught.exception.detail)
        with self.assertRaises(ValidationError):
            MossSettings(mode="r2i")
        with self.assertRaises(ValidationError):
            PresetCreateRequest(type="i2i_moss", name="unsupported", values={"prompt": "scene"})
        preset = PresetCreateRequest(type="t2i_moss", name="layout", values={"moss": {"layout_enabled": True}})
        self.assertTrue(preset.values.moss.layout_enabled)
