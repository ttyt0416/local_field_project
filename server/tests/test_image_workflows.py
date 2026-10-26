import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from model_fixtures import model_object_info

from app import comfyui
from app.auth import UserResponse
from app.configs.constants import settings


class ImageWorkflowFamilyTest(unittest.TestCase):
    def setUp(self):
        request = patch.object(comfyui, "_request_json", return_value=model_object_info())
        request.start()
        self.addCleanup(request.stop)

    def _request(self, family: comfyui.ModelFamily = "anima") -> comfyui.ImageGenerationRequest:
        checkpoint = (
            "Anima/anima_aestheticV11.safetensors"
            if family == "anima"
            else "Qwen/custom.safetensors"
            if family in comfyui._EDIT_MODELS
            else "Illustrious/unholyDesireMixSinister_v80.safetensors"
        )
        return comfyui.ImageGenerationRequest(
            model_family=family,
            prompt="1girl, portrait",
            negative_prompt="low quality",
            checkpoint=checkpoint,
            sampler_name="euler",
            scheduler="normal",
            width=768,
            height=1024,
            seed=123,
        )

    def test_anima_t2i_keeps_split_loader_contract(self) -> None:
        workflow, seed = comfyui._build_prompt(self._request("anima"))
        self.assertEqual(seed, 123)
        self.assertEqual(workflow["1"]["class_type"], "UNETLoader")
        self.assertEqual(workflow["3"]["class_type"], "CLIPLoader")
        self.assertEqual(workflow["4"]["class_type"], "VAELoader")
        self.assertEqual(workflow["7"]["class_type"], "EmptyLatentImage")
        self.assertEqual(workflow["8"]["inputs"]["denoise"], 1.0)

    def test_i2i_anima_and_illustrious_use_improved_prompt_and_keep_denoise(self) -> None:
        for family in ("anima", "illustrious"):
            with self.subTest(family=family):
                payload = comfyui.ImageToImageGenerationRequest(
                    **{**self._request(family).model_dump(), "prompt_enhancement_enabled": True, "improved_prompt": "portrait, soft lighting", "positive_prompt_prefix": "masterpiece"},
                    source={"file_index": 0}, denoise=0.55,
                )
                graph, _ = comfyui._build_prompt(payload, input_image="source.png", denoise=payload.denoise)
                self.assertEqual(graph["5"]["inputs"]["text"], "masterpiece, portrait, soft lighting")
                self.assertEqual(graph["8"]["inputs"]["denoise"], 0.55)
                payload.prompt_enhancement_enabled = False
                graph, _ = comfyui._build_prompt(payload, input_image="source.png", denoise=payload.denoise)
                self.assertEqual(graph["5"]["inputs"]["text"], "masterpiece, 1girl, portrait")

    def test_image_request_defaults_to_an_empty_negative_prompt(self) -> None:
        payload = comfyui.ImageGenerationRequest(prompt="portrait", checkpoint="Anima/anima_aestheticV11.safetensors")

        self.assertEqual(payload.negative_prompt, "")

    def test_image_dimensions_allow_native_maximum_and_reject_invalid_alignment(self) -> None:
        payload = comfyui.ImageGenerationRequest(prompt="portrait", checkpoint="Anima/anima_aestheticV11.safetensors", width=4096, height=16384)

        self.assertEqual((payload.width, payload.height), (4096, 16384))
        workflow, _ = comfyui._build_prompt(payload)
        self.assertEqual((workflow["7"]["inputs"]["width"], workflow["7"]["inputs"]["height"]), (4096, 16384))
        with self.assertRaises(ValidationError):
            comfyui.ImageGenerationRequest(prompt="portrait", checkpoint="Anima/anima_aestheticV11.safetensors", width=0)
        with self.assertRaises(ValidationError):
            comfyui.ImageGenerationRequest(prompt="portrait", checkpoint="Anima/anima_aestheticV11.safetensors", width=18)

    def test_image_request_accepts_more_than_eight_loras(self) -> None:
        payload = comfyui.ImageGenerationRequest(
            prompt="portrait",
            checkpoint="Anima/anima_aestheticV11.safetensors",
            loras=[comfyui.LoraSelection(name=f"style-{index}.safetensors", strength=1.0) for index in range(9)],
        )

        self.assertEqual(len(payload.loras), 9)

    def test_image_workflow_chains_more_than_eight_loras(self) -> None:
        payload = self._request("anima")
        payload.loras = [comfyui.LoraSelection(name=f"style-{index}.safetensors", strength=1.0) for index in range(9)]

        workflow, _ = comfyui._build_prompt(payload)

        self.assertEqual([workflow[str(index)]["inputs"]["lora_name"] for index in range(20, 29)], [lora.name for lora in payload.loras])
        self.assertEqual(workflow["28"]["inputs"]["model"], ["27", 0])

    def test_illustrious_t2i_uses_checkpoint_outputs(self) -> None:
        workflow, _ = comfyui._build_prompt(self._request("illustrious"))
        self.assertEqual(workflow["1"]["class_type"], "CheckpointLoaderSimple")
        self.assertNotIn("3", workflow)
        self.assertNotIn("4", workflow)
        self.assertEqual(workflow["5"]["inputs"]["clip"], ["1", 1])
        self.assertEqual(workflow["9"]["inputs"]["vae"], ["1", 2])

    def test_reference_upload_indices_are_complete_and_unique(self) -> None:
        request = comfyui.ImageToImageGenerationRequest(
            **self._request("qwen_image_2_1").model_dump(),
            source=comfyui.ImageSource(file_id="a" * 32),
            references=[comfyui.ImageSource(file_index=0), comfyui.ImageSource(file_id="b" * 32)],
        )
        comfyui._validate_image_sources(request, [object()])
        with self.assertRaises(HTTPException):
            comfyui._validate_image_sources(request, [])
        request.references.append(comfyui.ImageSource(file_index=0))
        with self.assertRaises(HTTPException):
            comfyui._validate_image_sources(request, [object()])
        request.model_family = "anima"
        with self.assertRaises(HTTPException):
            comfyui._validate_image_sources(request, [object()])

    def test_multi_reference_submission_preserves_storage_ids_and_order(self) -> None:
        request = comfyui.ImageToImageGenerationRequest(
            **self._request("qwen_image_2_1").model_dump(),
            source=comfyui.ImageSource(file_id="a" * 32),
            references=[comfyui.ImageSource(file_id="b" * 32), comfyui.ImageSource(file_id="c" * 32)],
        )
        async def resolve(source, files, user):
            return source.file_id, source.file_id + ".png", b"image", "image/png"
        with (
            patch.object(comfyui, "_image_options"), patch.object(comfyui, "_validate_model_choice"),
            patch.object(comfyui, "_resolve_image_source", side_effect=resolve),
            patch.object(comfyui, "_upload_comfy_input", side_effect=lambda content, filename, media_type: filename),
            patch.object(comfyui, "_submit_image_generation") as submit,
        ):
            asyncio.run(comfyui.create_image_to_image_generation(payload=request.model_dump_json(), files=[], user=UserResponse(id=uuid4(), username="tester")))
        self.assertEqual(submit.call_args.kwargs["input_references"], ["b" * 32 + ".png", "c" * 32 + ".png"])
        self.assertEqual([item["file_id"] for item in submit.call_args.kwargs["reference_images"]], ["b" * 32, "c" * 32])

    def test_edit_models_require_a_source_image(self) -> None:
        for family in comfyui._EDIT_MODELS:
            with self.subTest(family=family), self.assertRaises(HTTPException) as error:
                comfyui._build_prompt(self._request(family))
            self.assertEqual(error.exception.status_code, 422)

    def test_anima_i2i_scales_and_encodes_source(self) -> None:
        workflow, _ = comfyui._build_prompt(
            self._request("anima"), input_image="source.png", denoise=0.55
        )
        self.assertEqual(workflow["7"], {"class_type": "LoadImage", "inputs": {"image": "source.png"}})
        self.assertEqual(workflow["11"]["class_type"], "ImageScale")
        self.assertEqual(workflow["11"]["inputs"]["width"], 768)
        self.assertEqual(workflow["12"]["class_type"], "VAEEncode")
        self.assertEqual(workflow["12"]["inputs"]["vae"], ["4", 0])
        self.assertEqual(workflow["8"]["inputs"]["latent_image"], ["12", 0])
        self.assertEqual(workflow["8"]["inputs"]["denoise"], 0.55)

    def test_illustrious_i2i_uses_checkpoint_vae(self) -> None:
        workflow, _ = comfyui._build_prompt(
            self._request("illustrious"), input_image="source.png", denoise=0.7
        )
        self.assertEqual(workflow["12"]["inputs"]["vae"], ["1", 2])
        self.assertEqual(workflow["9"]["inputs"]["vae"], ["1", 2])
        self.assertIn("Illustrious_I2I", workflow["10"]["inputs"]["filename_prefix"])

    def test_node_choices_supports_classic_and_combo_options(self) -> None:
        classic = {"Node": {"input": {"required": {"value": [["b", "a"]]}}}}
        combo = {"Node": {"input": {"required": {"value": ["COMBO", {"options": ["b", "a"]}]}}}}

        self.assertEqual(comfyui._node_choices(classic, "Node", "value"), ["a", "b"])
        self.assertEqual(comfyui._node_choices(combo, "Node", "value"), ["a", "b"])

    def test_family_options_are_isolated(self) -> None:
        object_info = model_object_info()
        object_info["UNETLoader"]["input"]["required"]["unet_name"] = [["Anima/a.safetensors", "Qwen/custom.safetensors", "Other/x.safetensors"]]
        object_info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] = [["Illustrious/i.safetensors", "Other/y.safetensors"]]
        object_info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"] = [["Anima/lora.safetensors"]]
        object_info["LoraLoader"] = {"input": {"required": {"lora_name": [["Illustrious/lora.safetensors"]]}}}
        with patch.object(comfyui, "_request_json", return_value=object_info):
            anima = comfyui._image_options("anima")
            illustrious = comfyui._image_options("illustrious")
        self.assertEqual(anima.checkpoints, ["Anima/a.safetensors"])
        self.assertEqual(anima.loras, ["Anima/lora.safetensors"])
        self.assertEqual(illustrious.checkpoints, ["Illustrious/i.safetensors"])
        self.assertEqual(illustrious.loras, ["Illustrious/lora.safetensors"])

    def test_missing_illustrious_checkpoint_keeps_preset_options_available(self) -> None:
        object_info = {
            "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["yue2.safetensors"]]}}},
            "LoraLoader": {"input": {"required": {"lora_name": [["Illustrious/style.safetensors"]]}}},
            "KSampler": {"input": {"required": {"sampler_name": [["euler"]], "scheduler": [["normal"]]}}},
        }
        with patch.object(comfyui, "_request_json", return_value=object_info):
            options = comfyui._image_options("illustrious")

        self.assertEqual(options.checkpoints, [])
        self.assertEqual(options.default_checkpoint, "")
        self.assertEqual(options.loras, ["Illustrious/style.safetensors"])
        with self.assertRaises(HTTPException) as caught:
            comfyui._validate_model_choice(self._request("illustrious"), options)
        self.assertEqual(caught.exception.status_code, 422)

    def test_embedding_options_are_scoped_to_family_folder(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "embeddings"
            (root / "Illustrious").mkdir(parents=True)
            (root / "Anima").mkdir()
            (root / "Illustrious/style.safetensors").write_bytes(b"embedding")
            (root / "Anima/other.pt").write_bytes(b"embedding")
            with patch.object(
                comfyui, "settings", replace(settings, comfyui_models_path=temporary_directory)
            ):
                self.assertEqual(
                    comfyui._installed_family_files("embeddings", "Illustrious/"),
                    ["Illustrious/style.safetensors"],
                )

    def test_prompt_embedding_syntax_is_forwarded_unchanged(self) -> None:
        payload = self._request("illustrious")
        payload.prompt = "embedding:Illustrious/style, portrait"
        payload.negative_prompt = "embedding:Illustrious/bad-hands, low quality"
        workflow, _ = comfyui._build_prompt(payload)
        self.assertEqual(workflow["5"]["inputs"]["text"], payload.prompt)
        self.assertEqual(workflow["6"]["inputs"]["text"], payload.negative_prompt)

    def test_prompt_prefixes_are_composed_for_comfyui_conditioning(self) -> None:
        payload = self._request("anima")
        payload.positive_prompt_prefix = "cinematic lighting"
        payload.negative_prompt_prefix = "bad anatomy"

        workflow, _ = comfyui._build_prompt(payload)

        self.assertEqual(workflow["5"]["inputs"]["text"], "cinematic lighting, 1girl, portrait")
        self.assertEqual(workflow["6"]["inputs"]["text"], "bad anatomy, low quality")

    def test_submission_persists_prefixes_separately_from_prompt_bodies(self) -> None:
        payload = self._request("anima")
        payload.positive_prompt_prefix = "cinematic lighting"
        payload.negative_prompt_prefix = "bad anatomy"
        payload.prompt_enhancement_enabled = True
        payload.improved_prompt = "improved portrait"
        user = UserResponse(id=uuid4(), username="tester")
        created_at = datetime.now(timezone.utc)
        with (
            patch.object(comfyui, "_image_options"),
            patch.object(comfyui, "_validate_model_choice"),
            patch.object(comfyui, "_request_json", side_effect=lambda method, *args: model_object_info() if method == "GET" else {"prompt_id": "comfy-prompt"}),
            patch.object(comfyui, "create_image_generation_record", return_value=(uuid4(), created_at)) as create_record,
        ):
            comfyui._submit_image_generation(payload, user)

        self.assertEqual(create_record.call_args.kwargs["prompt"], "1girl, portrait")
        self.assertEqual(create_record.call_args.kwargs["improved_prompt"], "improved portrait")
        self.assertEqual(create_record.call_args.kwargs["positive_prompt_prefix"], "cinematic lighting")
        self.assertEqual(create_record.call_args.kwargs["negative_prompt"], "low quality")
        self.assertEqual(create_record.call_args.kwargs["negative_prompt_prefix"], "bad anatomy")

    def test_i2i_source_requires_exactly_one_reference(self) -> None:
        with self.assertRaises(ValidationError):
            comfyui.ImageSource()
        with self.assertRaises(ValidationError):
            comfyui.ImageSource(file_id="a" * 32, file_index=0)
        self.assertEqual(comfyui.ImageSource(file_index=0).file_index, 0)

    def test_removed_krea2_cannot_be_submitted(self) -> None:
        with self.assertRaises(ValidationError):
            comfyui.ImageGenerationRequest(model_family="krea2", prompt="portrait", checkpoint="old.safetensors")

    def test_edit_validation_rejects_misaligned_dimensions_and_generic_i2i_denoise(self) -> None:
        for family in comfyui._EDIT_MODELS:
            payload = comfyui.ImageToImageGenerationRequest(
                **{**self._request(family).model_dump(), "cfg": 1, "steps": comfyui._EDIT_MODELS[family]["steps"], "scheduler": comfyui._EDIT_MODELS[family].get("scheduler", "normal"), "prompt_enhancement_enabled": False},
                source=comfyui.ImageSource(file_index=0), denoise=1,
            )
            options = comfyui.ImageGenerationOptions(
                model_family=family, checkpoints=[payload.checkpoint], loras=[], embeddings=[],
                samplers=["euler"], schedulers=[payload.scheduler], default_checkpoint=payload.checkpoint,
                default_sampler="euler", default_scheduler="normal", default_cfg=1, default_steps=25,
            )
            comfyui._validate_model_choice(payload, options)
            payload.width = 776
            with self.assertRaises(HTTPException):
                comfyui._validate_model_choice(payload, options)
            payload.width = 768
            payload.denoise = 0.65
            with self.assertRaises(HTTPException):
                comfyui._validate_model_choice(payload, options)

    def test_i2i_reuses_owner_checked_generated_image_without_upload(self) -> None:
        source_file_id = "f" * 32
        user = UserResponse(id=uuid4(), username="tester")
        source = comfyui.ImageSource(file_id=source_file_id)
        generated = {
            "file_id": source_file_id,
            "filename": "generated-image.png",
            "content_type": "image/png",
            "media_kind": "image",
            "source_type": "image_generation",
        }
        with (
            patch.object(comfyui, "storage_enabled", return_value=True),
            patch.object(comfyui, "get_reusable_media", return_value=generated) as get_media,
            patch.object(comfyui, "storage_download_file", return_value=(b"image-bytes", "image/png")) as download,
            patch.object(comfyui, "storage_upload_file") as upload,
            patch.object(comfyui, "create_media_asset") as create_asset,
        ):
            result = asyncio.run(comfyui._resolve_image_source(source, [], user))

        self.assertEqual(result, (source_file_id, "generated-image.png", b"image-bytes", "image/png"))
        get_media.assert_called_once_with(source_file_id, user.id)
        download.assert_called_once_with(file_id=source_file_id, owner_id=str(user.id))
        upload.assert_not_called()
        create_asset.assert_called_once_with(
            user_id=user.id,
            storage_file_id=source_file_id,
            filename="generated-image.png",
            content_type="image/png",
            media_kind="image",
            size=len(b"image-bytes"),
        )


if __name__ == "__main__":
    unittest.main()
