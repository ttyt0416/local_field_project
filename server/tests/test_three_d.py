import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import three_d
from app.comfyui import _ComfyUIError


class ThreeDWorkflowTest(unittest.TestCase):
    def test_build_prompt_binds_source_preset_seed_and_background(self) -> None:
        request = three_d.ThreeDGenerationRequest(
            source=three_d.ThreeDSource(file_index=0),
            preset="high",
            seed=123,
            remove_background=False,
            padding=1.25,
        )

        prompt, seed = three_d._build_prompt(request, "input.png")

        self.assertEqual(seed, 123)
        self.assertEqual(prompt["122"]["inputs"]["image"], "input.png")
        self.assertFalse(prompt["248"]["inputs"]["switch"])
        self.assertEqual(prompt["312"]["inputs"]["pad_factor"], 1.25)
        self.assertEqual(prompt["94"]["inputs"]["target_resolution"], "1536")
        self.assertEqual(prompt["186"]["inputs"]["target_face_count"], 700_000)
        self.assertEqual(prompt["288"]["inputs"]["value"], 4096)
        self.assertTrue(prompt["900"]["inputs"]["filename_prefix"].startswith("LocalField_3D_"))
        self.assertEqual(
            {node["inputs"]["seed"] for node in prompt.values() if node["class_type"] == "KSampler"},
            {123},
        )

    def test_workflow_has_no_dangling_dependencies_and_one_glb_output(self) -> None:
        graph = json.loads(three_d._WORKFLOW_PATH.read_text(encoding="utf-8"))
        dangling = []
        for node_id, node in graph.items():
            for name, value in node["inputs"].items():
                if isinstance(value, list) and len(value) == 2 and value[0] not in graph:
                    dangling.append((node_id, name, value))

        self.assertEqual(dangling, [])
        self.assertIn("sign_mode.drop_enclosed_components", graph["241"]["inputs"])
        self.assertIn("sign_mode.drop_inverted_components", graph["241"]["inputs"])
        self.assertIn("sign_mode.qef", graph["241"]["inputs"])
        self.assertEqual(
            [node_id for node_id, node in graph.items() if node["class_type"] == "SaveGLB"],
            ["900"],
        )
        self.assertNotIn("nvdiffrast", three_d._WORKFLOW_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("nvdiffrec", three_d._WORKFLOW_PATH.read_text(encoding="utf-8"))

    def test_raw_model_output_accepts_only_glb(self) -> None:
        outputs = {
            "900": {
                "3d": [
                    {"filename": "ignored.obj", "subfolder": "", "type": "output"},
                    {"filename": "asset.glb", "subfolder": "models", "type": "output"},
                ]
            }
        }

        self.assertEqual(
            three_d._raw_model_output(outputs),
            {"filename": "asset.glb", "subfolder": "models", "type": "output"},
        )

    def test_sync_model_output_validates_magic_and_uploads_strict_mime(self) -> None:
        generation = {"prompt_id": "prompt", "storage_file_id": None}
        model = {"filename": "asset.glb", "subfolder": "", "type": "output"}
        with (
            patch.object(three_d, "_request_bytes", return_value=(b"glTF" + b"\0" * 20, "application/octet-stream")),
            patch.object(three_d, "storage_upload_file", return_value="file-id") as upload,
            patch.object(three_d, "update_three_d_generation_status") as update,
        ):
            three_d._sync_model_output(generation, model, uuid4())

        self.assertEqual(upload.call_args.kwargs["media_type"], "model/gltf-binary")
        self.assertEqual(update.call_args.kwargs["status"], "completed")
        self.assertEqual(update.call_args.kwargs["stage"], "completed")
        self.assertEqual(update.call_args.kwargs["size_bytes"], 24)

    def test_sync_model_output_rejects_non_glb_bytes(self) -> None:
        generation = {"prompt_id": "prompt", "storage_file_id": None}
        model = {"filename": "asset.glb", "subfolder": "", "type": "output"}
        with (
            patch.object(three_d, "_request_bytes", return_value=(b"not a glb file", "application/octet-stream")),
            patch.object(three_d, "storage_upload_file") as upload,
            patch.object(three_d, "update_three_d_generation_status"),
            self.assertRaises(_ComfyUIError),
        ):
            three_d._sync_model_output(generation, model, uuid4())
        upload.assert_not_called()

    def test_readiness_supports_classic_and_combo_options(self) -> None:
        graph = json.loads(Path(three_d._WORKFLOW_PATH).read_text(encoding="utf-8"))
        info = {node["class_type"]: {"input": {"required": {}}} for node in graph.values()}
        info["UNETLoader"]["input"]["required"]["unet_name"] = [["trellis_2_int8_convrot.safetensors"]]
        info["CLIPVisionLoader"]["input"]["required"]["clip_name"] = [["dino_v3_vit_l.safetensors"]]
        info["VAELoader"]["input"]["required"]["vae_name"] = [[
            "trellis_2_shape_vae_bf16.safetensors",
            "trellis_2_texture_vae_bf16.safetensors",
        ]]
        info["LoadBackgroundRemovalModel"]["input"]["required"]["bg_removal_name"] = [
            "COMBO",
            {"options": ["birefnet.safetensors"]},
        ]

        with patch.object(three_d, "_request_json", return_value=info):
            self.assertEqual(three_d._readiness(), ([], []))


if __name__ == "__main__":
    unittest.main()
