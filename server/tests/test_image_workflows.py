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

from app import comfyui
from app.auth import UserResponse
from app.configs.constants import settings


class ImageWorkflowFamilyTest(unittest.TestCase):
    def _request(self, family: comfyui.ModelFamily = "anima") -> comfyui.ImageGenerationRequest:
        checkpoint = (
            "Anima/anima_aestheticV11.safetensors"
            if family == "anima"
            else "Krea/krea2TurboOfficialComfy_krea2TurboNvfp4.safetensors"
            if family == "krea2"
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

    def test_image_request_defaults_to_an_empty_negative_prompt(self) -> None:
        payload = comfyui.ImageGenerationRequest(prompt="portrait", checkpoint="Anima/anima_aestheticV11.safetensors")

        self.assertEqual(payload.negative_prompt, "")

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

    def test_krea2_t2i_uses_the_official_turbo_contract(self) -> None:
        payload = self._request("krea2")
        payload.cfg = 1
        payload.steps = 8
        payload.scheduler = "simple"
        workflow, _ = comfyui._build_prompt(payload)
        self.assertEqual(workflow["1"]["class_type"], "UNETLoader")
        self.assertEqual(workflow["3"]["inputs"]["clip_name"], "qwen3vl_4b_fp8_scaled.safetensors")
        self.assertEqual(workflow["3"]["inputs"]["type"], "krea2")
        self.assertEqual(workflow["4"]["inputs"]["vae_name"], "qwen_image_vae.safetensors")
        self.assertEqual(workflow["6"]["class_type"], "ConditioningZeroOut")
        self.assertEqual(workflow["8"]["inputs"]["steps"], 8)
        self.assertEqual(workflow["8"]["inputs"]["cfg"], 1)

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
        object_info = {
            "UNETLoader": {"input": {"required": {"unet_name": [["Anima/a.safetensors", "Krea/krea2TurboOfficialComfy_krea2TurboNvfp4.safetensors", "Other/x.safetensors"]]}}},
            "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["Illustrious/i.safetensors", "Other/y.safetensors"]]}}},
            "LoraLoaderModelOnly": {"input": {"required": {"lora_name": [["Anima/lora.safetensors"]]}}},
            "LoraLoader": {"input": {"required": {"lora_name": [["Illustrious/lora.safetensors"]]}}},
            "CLIPLoader": {"input": {"required": {"clip_name": [["qwen3vl_4b_fp8_scaled.safetensors"]]}}},
            "VAELoader": {"input": {"required": {"vae_name": [["qwen_image_vae.safetensors"]]}}},
            "KSampler": {"input": {"required": {"sampler_name": [["er_sde"]], "scheduler": [["simple"]]}}},
        }
        with patch.object(comfyui, "_request_json", return_value=object_info):
            anima = comfyui._image_options("anima")
            illustrious = comfyui._image_options("illustrious")
            krea2 = comfyui._image_options("krea2")
        self.assertEqual(anima.checkpoints, ["Anima/a.safetensors"])
        self.assertEqual(anima.loras, ["Anima/lora.safetensors"])
        self.assertEqual(illustrious.checkpoints, ["Illustrious/i.safetensors"])
        self.assertEqual(illustrious.loras, ["Illustrious/lora.safetensors"])
        self.assertEqual(krea2.checkpoints, ["Krea/krea2TurboOfficialComfy_krea2TurboNvfp4.safetensors"])
        self.assertEqual(krea2.default_cfg, 1)
        self.assertEqual(krea2.default_steps, 8)

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

    def test_submission_persists_composed_prompt_values_for_vault(self) -> None:
        payload = self._request("anima")
        payload.positive_prompt_prefix = "cinematic lighting"
        payload.negative_prompt_prefix = "bad anatomy"
        user = UserResponse(id=uuid4(), username="tester")
        created_at = datetime.now(timezone.utc)
        with (
            patch.object(comfyui, "_image_options"),
            patch.object(comfyui, "_validate_model_choice"),
            patch.object(comfyui, "_request_json", return_value={"prompt_id": "comfy-prompt"}),
            patch.object(comfyui, "create_image_generation_record", return_value=(uuid4(), created_at)) as create_record,
        ):
            comfyui._submit_image_generation(payload, user)

        self.assertEqual(create_record.call_args.kwargs["prompt"], "cinematic lighting, 1girl, portrait")
        self.assertEqual(create_record.call_args.kwargs["negative_prompt"], "bad anatomy, low quality")

    def test_i2i_source_requires_exactly_one_reference(self) -> None:
        with self.assertRaises(ValidationError):
            comfyui.ImageSource()
        with self.assertRaises(ValidationError):
            comfyui.ImageSource(file_id="a" * 32, file_index=0)
        self.assertEqual(comfyui.ImageSource(file_index=0).file_index, 0)

    def test_krea2_i2i_requires_its_dedicated_reference_workflow(self) -> None:
        user = UserResponse(id=uuid4(), username="tester")
        request = comfyui.ImageToImageGenerationRequest(
            **self._request("krea2").model_dump(),
            source=comfyui.ImageSource(file_id="f" * 32),
        )
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                comfyui.create_image_to_image_generation(
                    payload=request.model_dump_json(), files=[], user=user
                )
            )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("style-reference", str(raised.exception.detail))

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
