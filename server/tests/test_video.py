import asyncio
import json
import re
import unittest
from pathlib import Path
from typing import Literal, cast
from unittest.mock import call, patch
from uuid import uuid4

from app import video
from app.auth import UserResponse
from app.comfyui import cancel_comfy_generation
from pydantic import ValidationError


class VideoContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user = UserResponse(id=uuid4(), username="tester")

    def test_minimax_workflows_have_no_default_loras(self) -> None:
        workflows = Path(video.__file__).with_name("workflows")
        for filename in ("video_i2v.json", "video_fl2v.json", "video_r2v.json"):
            workflow = json.loads((workflows / filename).read_text())
            unet = next(node for node in workflow.values() if node["class_type"] == "UNETLoader")
            loras = [(node_id, node) for node_id, node in workflow.items() if node["class_type"] == "LoraLoaderModelOnly"]
            sampler = next(node for node in workflow.values() if node["class_type"] == "KSamplerSelect")
            scheduler = next(node for node in workflow.values() if node["class_type"] == "BasicScheduler")

            self.assertEqual(unet["inputs"]["unet_name"], video._DASIWA_CHECKPOINT)
            self.assertEqual(loras, [])
            self.assertEqual(sampler["inputs"]["sampler_name"], "res_multistep")
            self.assertEqual(scheduler["inputs"], {"model": ["1", 0], "scheduler": "simple", "steps": 4, "denoise": 1})

    def test_video_checkpoint_options_exclude_general_minimax_and_default_to_dasiwa(self) -> None:
        available = [
            video._EROS_CHECKPOINT,
            video._DASIWA_CHECKPOINT,
            "MiniMaxH3/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
            "MiniMaxH3/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
        ]
        object_info = {
            "UNETLoader": {"input": {"required": {"unet_name": [available]}}},
            "KSamplerSelect": {"input": {"required": {"sampler_name": [["res_multistep", "euler"]]}}},
            "BasicScheduler": {"input": {"required": {"scheduler": [["simple", "normal"]]}}},
            "LoraLoaderModelOnly": {
                "input": {"required": {"lora_name": [["MiniMax/allowed.safetensors", "image/ignored.safetensors"]]}}
            },
        }
        with patch.object(video, "_request_json", return_value=object_info):
            options = video._video_options("r2v")
            with self.assertRaises(video.HTTPException):
                video._validated_video_checkpoint("r2v", "MiniMaxH3/minimax_h3_ref2va_pruned_int8_convrot.safetensors")

        self.assertEqual(options.checkpoints, [video._EROS_CHECKPOINT, video._DASIWA_CHECKPOINT])
        self.assertEqual(options.default_checkpoint, video._DASIWA_CHECKPOINT)
        self.assertEqual(options.loras, ["MiniMax/allowed.safetensors"])
        self.assertEqual(options.samplers, ["euler", "res_multistep"])
        self.assertEqual(options.schedulers, ["normal", "simple"])
        self.assertFalse(options.pdd_available)
        self.assertFalse(options.learned_upscale_available)


    def test_video_options_detects_learned_upscale_v3_combo_model(self) -> None:
        object_info = {
            "UNETLoader": {"input": {"required": {"unet_name": [[video._DASIWA_CHECKPOINT]]}}},
            "KSamplerSelect": {"input": {"required": {"sampler_name": [["res_multistep"]]}}},
            "BasicScheduler": {"input": {"required": {"scheduler": [["simple"]]}}},
            "LoraLoaderModelOnly": {"input": {"required": {"lora_name": [[]]}}},
            video._LEARNED_UPSCALE_NODE: {"input": {"required": {"model_name": ["COMBO", {"options": [video._LEARNED_UPSCALE_MODEL]}]}}},
            "LTXVSeparateAVLatent": {"input": {"required": {}}},
            "LTXVConcatAVLatent": {"input": {"required": {}}},
        }
        with patch.object(video, "_request_json", return_value=object_info):
            options = video._video_options("i2v")

        self.assertTrue(options.learned_upscale_available)


    def test_video_workflows_do_not_clean_vram_automatically(self) -> None:
        workflows = Path(video.__file__).with_name("workflows")
        for filename in (
            "video_i2v.json",
            "video_fl2v.json",
            "video_r2v.json",

        ):
            workflow = json.loads((workflows / filename).read_text())
            self.assertNotIn("0", workflow)

        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        request = video.VideoGenerationRequest(prompt="move", seed=1, first_frame=video.VideoAsset(kind="image", file_index=0))
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            first, _ = video._build_prompt("i2v", request, resolved)
            second, _ = video._build_prompt("i2v", request, resolved)
        self.assertNotIn("0", first)
        self.assertNotIn("0", second)

    def test_minimax_loras_are_allowlisted_and_injected_in_selection_order(self) -> None:
        options = video.VideoGenerationOptions(
            mode="i2v",
            checkpoints=[video._DASIWA_CHECKPOINT],
            default_checkpoint=video._DASIWA_CHECKPOINT,
            loras=["MiniMax/first.safetensors", "MiniMax/second.safetensors"],
        )
        lora_selection = [
            video.VideoLoraSelection(name="MiniMax/first.safetensors", strength=0.7),
            video.VideoLoraSelection(name="MiniMax/second.safetensors", strength=1.2),
        ]
        requests: dict[Literal["i2v", "fl2v", "r2v"], video.VideoGenerationRequest] = {
            "i2v": video.VideoGenerationRequest(prompt="move", checkpoint=video._DASIWA_CHECKPOINT, loras=lora_selection, first_frame=video.VideoAsset(kind="image", file_index=0)),
            "fl2v": video.VideoGenerationRequest(prompt="move", checkpoint=video._DASIWA_CHECKPOINT, loras=lora_selection, first_frame=video.VideoAsset(kind="image", file_index=0), last_frame=video.VideoAsset(kind="image", file_index=1)),
            "r2v": video.VideoGenerationRequest(prompt="move", checkpoint=video._DASIWA_CHECKPOINT, loras=lora_selection, reference_images=[video.VideoAsset(kind="image", file_index=0)]),
        }
        resolved = {
            "index:0": video._ResolvedAsset(file_id="a" * 32, filename="first.png", content=b"i", media_type="image/png", kind="image"),
            "index:1": video._ResolvedAsset(file_id="b" * 32, filename="last.png", content=b"i", media_type="image/png", kind="image"),
        }
        with patch.object(video, "_video_options", return_value=options), patch.object(video, "_upload_to_comfy", return_value="image.png"):
            for mode, request in requests.items():
                video._validate_video_loras(mode, request)
                prompt, _ = video._build_prompt(mode, request, resolved)
                loras = [(node_id, node) for node_id, node in prompt.items() if node["class_type"] == "LoraLoaderModelOnly"]
                scheduler = next(node for node in prompt.values() if node["class_type"] == "BasicScheduler")
                guider = next(node for node in prompt.values() if node["class_type"] == "BasicGuider")
                sage_id, sage = next((node_id, node) for node_id, node in prompt.items() if node["class_type"] == "PathchSageAttentionKJ")
                sol_id, sol = next((node_id, node) for node_id, node in prompt.items() if node["class_type"] == "SolAttnPatch")
                cache_id, cache = next((node_id, node) for node_id, node in prompt.items() if node["class_type"] == "EasyCache")
                self.assertEqual([node["inputs"]["lora_name"] for _, node in loras], ["MiniMax/first.safetensors", "MiniMax/second.safetensors"])
                self.assertEqual(loras[0][1]["inputs"]["model"], ["1", 0])
                self.assertEqual(loras[1][1]["inputs"]["model"], [loras[0][0], 0])
                self.assertEqual(sage["inputs"], {"model": [loras[1][0], 0], "sage_attention": "auto", "allow_compile": False})
                self.assertEqual(
                    sol["inputs"],
                    {
                        "model": [sage_id, 0],
                        "tau": 1.2,
                        "start_percent": 0.2,
                        "end_percent": 0.8,
                        "min_tokens": 4096,
                        "int8_qk": True,
                        "sink_conditioning": "exact_kv",
                        "morton": False,
                        "morton_curve": "2d_frame",
                        "int8_pv": True,
                        "verbose": False,
                        "use_tma": False,
                        "dense_blocks": "",
                    },
                )
                self.assertEqual(cache["inputs"], {"model": [sol_id, 0], "reuse_threshold": 0.3, "start_percent": 0.2, "end_percent": 0.9, "verbose": False})
                self.assertEqual(scheduler["inputs"]["model"], [cache_id, 0])
                self.assertEqual(guider["inputs"]["model"], [cache_id, 0])

    def test_video_lora_rejects_unknown_artifacts(self) -> None:
        options = video.VideoGenerationOptions(
            mode="i2v",
            checkpoints=[video._DASIWA_CHECKPOINT],
            default_checkpoint=video._DASIWA_CHECKPOINT,
            loras=["MiniMax/allowed.safetensors"],
        )
        with patch.object(video, "_video_options", return_value=options):
            with self.assertRaises(video.HTTPException):
                video._validate_video_loras("i2v", video.VideoGenerationRequest(prompt="move", checkpoint=video._DASIWA_CHECKPOINT, loras=[video.VideoLoraSelection(name="MiniMax/unknown.safetensors")]))

    def test_eros_checkpoint_uses_six_steps_without_default_loras(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            checkpoint=video._EROS_CHECKPOINT,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            prompt, _ = video._build_prompt("i2v", request, resolved)

        unet = next(node for node in prompt.values() if node["class_type"] == "UNETLoader")
        loras = [(node_id, node) for node_id, node in prompt.items() if node["class_type"] == "LoraLoaderModelOnly"]
        scheduler = next(node for node in prompt.values() if node["class_type"] == "BasicScheduler")
        sage_id, sage = next((node_id, node) for node_id, node in prompt.items() if node["class_type"] == "PathchSageAttentionKJ")
        sol_id, sol = next((node_id, node) for node_id, node in prompt.items() if node["class_type"] == "SolAttnPatch")
        cache_id, cache = next((node_id, node) for node_id, node in prompt.items() if node["class_type"] == "EasyCache")
        self.assertEqual(unet["inputs"]["unet_name"], video._EROS_CHECKPOINT)
        self.assertEqual(loras, [])
        self.assertEqual(sage["inputs"]["model"], ["1", 0])
        self.assertEqual(sol["inputs"]["model"], [sage_id, 0])
        self.assertEqual(cache["inputs"]["model"], [sol_id, 0])
        self.assertEqual(scheduler["inputs"]["model"], [cache_id, 0])
        self.assertEqual(scheduler["inputs"]["steps"], 6)

    def test_video_sampling_is_written_to_comfy_nodes(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            sampler_name="euler",
            scheduler="normal",
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            prompt, _ = video._build_prompt("i2v", request, resolved)

        sampler = next(node for node in prompt.values() if node["class_type"] == "KSamplerSelect")
        scheduler = next(node for node in prompt.values() if node["class_type"] == "BasicScheduler")
        self.assertEqual(sampler["inputs"]["sampler_name"], "euler")
        self.assertEqual(scheduler["inputs"]["scheduler"], "normal")

    def test_pdd_uses_its_sigma_schedule_and_disables_easycache(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            checkpoint=video._DASIWA_CHECKPOINT,
            steps=6,
            use_pdd=True,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            prompt, _ = video._build_prompt("i2v", request, resolved)

        pdd_id, pdd = next((node_id, node) for node_id, node in prompt.items() if node["class_type"] == "MiniMaxH3PDDAccApply")
        sampler = next(node for node in prompt.values() if node["class_type"] == "KSamplerSelect")
        sample = next(node for node in prompt.values() if node["class_type"] == "SamplerCustomAdvanced")
        scheduler = next(node for node in prompt.values() if node["class_type"] == "BasicScheduler")
        self.assertEqual(pdd["inputs"]["pdd_file"], video._PDD_FILES["ref2va"])
        self.assertEqual(pdd["inputs"]["nfe"], "6")
        self.assertEqual(pdd["inputs"]["on_off_grid"], "error")
        self.assertEqual(pdd["inputs"]["partition_check"], "error")
        self.assertEqual(sampler["inputs"]["sampler_name"], "euler")
        self.assertEqual(sample["inputs"]["sigmas"], [pdd_id, 1])
        self.assertEqual(scheduler["inputs"]["steps"], 6)
        self.assertFalse(any(node["class_type"] == "EasyCache" for node in prompt.values()))

    def test_pdd_rejects_unsupported_steps_and_requires_live_artifacts(self) -> None:
        options = video.VideoGenerationOptions(
            mode="i2v",
            checkpoints=[video._DASIWA_CHECKPOINT],
            default_checkpoint=video._DASIWA_CHECKPOINT,
            loras=[],
            pdd_available=True,
        )
        with patch.object(video, "_video_options", return_value=options):
            video._validate_video_pdd("i2v", video.VideoGenerationRequest(prompt="move", use_pdd=True, steps=8))
            with self.assertRaises(video.HTTPException):
                video._validate_video_pdd("i2v", video.VideoGenerationRequest(prompt="move", use_pdd=True, steps=5))

    def test_continuation_defaults_to_and_keeps_dasiwa_profile(self) -> None:
        default_model, default_checkpoint = video._workflow_checkpoint("r2v", None)
        selected_model, selected_checkpoint = video._workflow_checkpoint("r2v", video._DASIWA_CHECKPOINT)

        self.assertEqual(default_model, "dasiwa")
        self.assertEqual(default_checkpoint, video._DASIWA_CHECKPOINT)
        self.assertEqual(selected_model, "dasiwa")
        self.assertEqual(selected_checkpoint, video._DASIWA_CHECKPOINT)


    def test_reference_markers_are_normalized_to_minimax_contract(self) -> None:
        self.assertEqual(
            video._normalize_video_reference_markers("[Image1] @video2 [Audio 3]"),
            "<Picture 1> <Video 2> <Audio 3>",
        )

    def test_cancel_comfy_prompt_uses_native_target_cancel(self) -> None:
        with patch("app.comfyui._request_json", return_value={"cancelled": True}) as request_json:
            self.assertTrue(cancel_comfy_generation("prompt-1"))
        request_json.assert_called_once_with("POST", "/api/jobs/prompt-1/cancel")

    def test_cancel_comfy_prompt_preserves_native_noop(self) -> None:
        with patch("app.comfyui._request_json", return_value={"cancelled": False}) as request_json:
            self.assertFalse(cancel_comfy_generation("prompt-2"))
        request_json.assert_called_once_with("POST", "/api/jobs/prompt-2/cancel")

        requests = {
            "i2v": video.VideoGenerationRequest(
                prompt="move",
                first_frame=video.VideoAsset(kind="image", file_index=0),
            ),
            "fl2v": video.VideoGenerationRequest(
                prompt="move",
                first_frame=video.VideoAsset(kind="image", file_index=0),
                last_frame=video.VideoAsset(kind="image", file_index=1),
            ),
            "r2v": video.VideoGenerationRequest(
                prompt="move <Picture 1> <Audio 1>",
                reference_images=[video.VideoAsset(kind="image", file_index=0)],
                reference_audios=[video.VideoAsset(kind="audio", file_index=1)],
            ),
        }
        resolved = {
            "index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image"),
            "index:1": video._ResolvedAsset(file_id="b" * 32, filename="voice.wav", content=b"a", media_type="audio/wav", kind="audio"),
        }
        with patch.object(video, "_upload_to_comfy", side_effect=lambda _resolved, asset, _kind: f"{asset.file_index}.input"):
            for mode, request in requests.items():
                prompt, _ = video._build_prompt(mode, request, resolved)
                save = next(node for node in prompt.values() if node["class_type"] == "SaveVideo")
                self.assertEqual(save["inputs"]["format"], "mp4")
                self.assertEqual(save["inputs"]["codec"], "h264")
                generator = next(
                    node
                    for node in prompt.values()
                    if node["class_type"] in {"MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"}
                )
                self.assertEqual(generator["inputs"]["prompt"], request.prompt)

    def test_fps_defaults_to_24_and_reaches_video_workflow(self) -> None:
        self.assertEqual(video.VideoGenerationRequest(prompt="move").fps, 24)
        request = video.VideoGenerationRequest(
            prompt="move",
            duration=3,
            fps=30,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            prompt, _ = video._build_prompt("i2v", request, resolved)

        generator = next(node for node in prompt.values() if node["class_type"] == "MiniMaxH3ImageToVideo")
        create_video = next(node for node in prompt.values() if node["class_type"] == "CreateVideo")
        self.assertEqual(generator["inputs"]["length"], video._frame_length(3, 30))
        self.assertEqual(create_video["inputs"]["fps"], 30)

    def test_video_dimensions_are_calculated_from_ratio_and_one_decimal_megapixels(self) -> None:
        request = video.VideoGenerationRequest(prompt="move", aspect_ratio="2:3", megapixels=0.24, first_frame=video.VideoAsset(kind="image", file_index=0))

        self.assertEqual(request.megapixels, 0.2)
        self.assertEqual((request.width, request.height), (384, 576))
        self.assertEqual(round(request.width * request.height / 1_000_000, 1), 0.2)
        self.assertFalse({"width", "height"} & video.VideoGenerationRequest.model_json_schema()["properties"].keys())
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            workflow, _ = video._build_prompt("i2v", request, resolved)
        generator = next(node for node in workflow.values() if node["class_type"] == "MiniMaxH3ImageToVideo")
        self.assertEqual((generator["inputs"]["width"], generator["inputs"]["height"]), (384, 576))
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", megapixels=0.04)
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest.model_validate({"prompt": "move", "width": 352, "height": 528})

    def test_learned_upscale_keeps_base_generation_and_injects_target_only_path(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            aspect_ratio="2:3",
            megapixels=0.2,
            upscale_mode="learned_3d",
            target_megapixels=0.4,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="image.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="image.png"):
            workflow, _ = video._build_prompt("i2v", request, resolved)

        generator = next(node for node in workflow.values() if node["class_type"] == "MiniMaxH3ImageToVideo")
        sampler_id = next(node_id for node_id, node in workflow.items() if node["class_type"] == "SamplerCustomAdvanced")
        separate_id, separate = next((node_id, node) for node_id, node in workflow.items() if node["class_type"] == "LTXVSeparateAVLatent")
        upscale_id, upscale = next((node_id, node) for node_id, node in workflow.items() if node["class_type"] == video._LEARNED_UPSCALE_NODE)
        concat_id, concat = next((node_id, node) for node_id, node in workflow.items() if node["class_type"] == "LTXVConcatAVLatent")
        decode = next(node for node in workflow.values() if node["class_type"] == "VAEDecode")

        self.assertEqual((request.width, request.height), (384, 576))
        self.assertEqual((request.output_width, request.output_height), (512, 768))
        self.assertNotEqual(request.effective_upscale_scale, 1.5)
        self.assertEqual((generator["inputs"]["width"], generator["inputs"]["height"]), (request.width, request.height))
        self.assertEqual(separate["inputs"], {"av_latent": [sampler_id, 0]})
        self.assertEqual(upscale["inputs"]["latent"], [separate_id, 0])
        self.assertEqual(upscale["inputs"]["model_name"], video._LEARNED_UPSCALE_MODEL)
        self.assertEqual(upscale["inputs"]["mode"], "target dimensions")
        self.assertEqual((upscale["inputs"]["mode.width"], upscale["inputs"]["mode.height"]), (request.output_width, request.output_height))
        self.assertEqual(upscale["inputs"]["align"], 32)
        self.assertEqual(concat["inputs"], {"video_latent": [upscale_id, 0], "audio_latent": [separate_id, 1]})
        self.assertEqual(decode["inputs"]["samples"], [concat_id, 0])
        self.assertFalse(any(node["class_type"] == "MiniMaxH3PDDAccApply" for node in workflow.values()))

    def test_learned_upscale_requires_a_larger_target_and_no_pdd(self) -> None:
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", megapixels=0.2, upscale_mode="learned_3d", target_megapixels=0.2)
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", megapixels=0.2, upscale_mode="learned_3d", target_megapixels=0.4, use_pdd=True)
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", target_megapixels=0.4)

    def test_legacy_16_grid_dimensions_are_not_reused_for_h3_continuation(self) -> None:
        request = video.VideoGenerationRequest(prompt="move", aspect_ratio="2:3", megapixels=0.2)

        video._keep_generation_dimensions(request, {"width": 352, "height": 528})

        self.assertEqual((request.width, request.height), (384, 576))

    def test_learned_upscale_requires_live_model_and_node(self) -> None:
        request = video.VideoGenerationRequest(prompt="move", megapixels=0.2, upscale_mode="learned_3d", target_megapixels=0.4)
        unavailable = video.VideoGenerationOptions(mode="i2v", checkpoints=[], default_checkpoint="", loras=[])
        available = video.VideoGenerationOptions(mode="i2v", checkpoints=[], default_checkpoint="", loras=[], learned_upscale_available=True)
        with patch.object(video, "_video_options", return_value=unavailable):
            with self.assertRaises(video.HTTPException):
                video._validate_learned_upscale("i2v", request)
        with patch.object(video, "_video_options", return_value=available):
            video._validate_learned_upscale("i2v", request)

    def test_reference_media_never_sets_output_dimensions(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move <Picture 1>",
            aspect_ratio="2:3",
            megapixels=0.2,
            reference_images=[video.VideoAsset(kind="image", file_index=0)],
        )
        resolved = {"index:0": video._ResolvedAsset(file_id="a" * 32, filename="large-source.png", content=b"i", media_type="image/png", kind="image")}
        with patch.object(video, "_upload_to_comfy", return_value="large-source.png"):
            workflow, _ = video._build_prompt("r2v", request, resolved)

        generator = next(node for node in workflow.values() if "width" in node["inputs"] and "height" in node["inputs"])
        self.assertEqual((generator["inputs"]["width"], generator["inputs"]["height"]), (384, 576))

    def test_fps_validation_rejects_values_outside_supported_range(self) -> None:
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", fps=0)
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", fps=121)

    def test_duration_has_no_fixed_bounds(self) -> None:
        request = video.VideoGenerationRequest(prompt="move", duration=100)
        enhancement = video.VideoPromptEnhancementRequest(prompt="move", mode="i2v", duration=0)
        self.assertEqual(request.duration, 100)
        self.assertEqual(enhancement.duration, 0)

    def test_long_video_accepts_one_full_prompt_for_every_raw_segment(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="opening to ending",
            duration=23,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )

        self.assertEqual(video._video_segment_durations(request.duration), [10.0, 10.0, 3.0])
        prompts = video._effective_video_prompts("i2v", request)
        self.assertEqual(prompts[0], "opening to ending")
        self.assertTrue(all("<Picture 1>: actual final frame" in prompt for prompt in prompts[1:]))
        with self.assertRaises(video.HTTPException):
            video._effective_video_prompts("i2v", request.model_copy(update={"segment_prompts": ["opening"]}))

    def test_long_video_combines_global_context_with_each_segment_prompt(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="hand-drawn animation in a forest at dawn",
            segment_prompts=["The character enters the forest.", "The character finds a river.", "The character leaves at sunset."],
            duration=23,
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )

        prompts = video._effective_video_prompts("i2v", request)
        self.assertEqual(
            prompts[0],
            "Overall style and background:\nhand-drawn animation in a forest at dawn\n\nCurrent segment:\nThe character enters the forest.",
        )
        self.assertTrue(all("<Picture 1>: actual final frame" in prompt for prompt in prompts[1:]))
        self.assertIn("The character finds a river.", prompts[1])
        self.assertIn("The character leaves at sunset.", prompts[2])

    def test_r2v_continuation_uses_last_frame_as_picture_one_and_keeps_selected_images(self) -> None:
        generation = {
            "prompt_id": "root-prompt",
            "client_id": "client-1",
            "segment_index": 0,
            "segment_durations": [10.0, 10.0, 3.0],
            "segment_prompts": ["opening", "continuation", "final"],
            "continuation_mode": "r2v",
            "reference_image_file_ids": ["a" * 32],
            "width": 768,
            "height": 1344,
            "fps": 24,
            "seed": 7,
        }
        captured: dict[str, object] = {}

        def build(mode, request, resolved, *, effective_prompt):
            captured.update(mode=mode, request=request, resolved=resolved, effective_prompt=effective_prompt)
            return {}, 7

        with (
            patch.object(video, "_build_prompt", side_effect=build),
            patch.object(video, "_request_json", return_value={"prompt_id": "r2v-prompt"}) as submit,
            patch.object(video, "storage_download_file", return_value=(b"selected-reference", "image/png")),
        ):
            prompt_id = video._queue_video_continuation(generation, self.user.id, "f" * 32, b"last-frame")

        request = cast(video.VideoGenerationRequest, captured["request"])
        resolved = cast(dict[str, video._ResolvedAsset], captured["resolved"])
        self.assertEqual(prompt_id, "r2v-prompt")
        self.assertTrue(submit.call_args.args[2]["local_field_vram_cleanup_after"])
        self.assertEqual(captured["mode"], "r2v")
        self.assertEqual(captured["effective_prompt"], "continuation")
        self.assertEqual(request.duration, 10.0)
        self.assertEqual(
            request.reference_images,
            [video.VideoAsset(kind="image", file_id="f" * 32), video.VideoAsset(kind="image", file_id="a" * 32)],
        )
        self.assertEqual(resolved["id:" + "f" * 32].content, b"last-frame")
        self.assertEqual(resolved["id:" + "a" * 32].content, b"selected-reference")

    def test_i2v_continuation_uses_last_frame_as_first_frame(self) -> None:
        generation = {
            "prompt_id": "root-prompt",
            "client_id": "client-1",
            "segment_index": 0,
            "segment_durations": [10.0, 3.0],
            "segment_prompts": ["opening", "continuation"],
            "continuation_mode": "i2v",
            "width": 768,
            "height": 1344,
            "fps": 24,
            "seed": 7,
        }
        captured: dict[str, object] = {}

        def build(mode, request, resolved, *, effective_prompt):
            captured.update(mode=mode, request=request, resolved=resolved, effective_prompt=effective_prompt)
            return {}, 7

        with (
            patch.object(video, "_build_prompt", side_effect=build),
            patch.object(video, "_request_json", return_value={"prompt_id": "i2v-prompt"}) as submit,
        ):
            video._queue_video_continuation(generation, self.user.id, "f" * 32, b"last-frame")

        request = cast(video.VideoGenerationRequest, captured["request"])
        self.assertNotIn("local_field_vram_cleanup_after", submit.call_args.args[2])
        self.assertEqual(captured["mode"], "i2v")
        self.assertEqual(request.first_frame, video.VideoAsset(kind="image", file_id="f" * 32))
        self.assertEqual(request.reference_images, [])

    def test_long_r2v_rejects_nine_selected_images(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            duration=11,
            reference_images=[video.VideoAsset(kind="image", file_id=f"{index:032x}") for index in range(9)],
        )

        with self.assertRaises(video.HTTPException) as raised:
            video._validate_request("r2v", request, [])

        self.assertEqual(raised.exception.status_code, 422)

    def test_r2v_continuation_prompt_reserves_picture_one_for_the_actual_last_frame(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="global style",
            duration=11,
            segment_prompts=["opening", "continuation"],
            reference_images=[video.VideoAsset(kind="image", file_id="a" * 32)],
        )

        continuation_prompt = video._effective_video_prompts("r2v", request)[1]

        self.assertIn("<Picture 1>: actual final frame", continuation_prompt)
        self.assertIn("<Picture 2>: user-selected reference image", continuation_prompt)

    def test_completed_segment_extracts_last_frame_before_r2v_transition(self) -> None:
        generation = {
            "prompt_id": "root-prompt",
            "active_prompt_id": None,
            "client_id": "client-1",
            "user_id": self.user.id,
            "segment_index": 0,
            "segment_durations": [10.0, 3.0],
            "segment_prompts": ["opening", "continuation"],
            "segment_file_ids": [],
            "width": 768,
            "height": 1344,
            "fps": 24,
            "seed": 7,
            "status": "processing",
        }
        with (
            patch.object(video, "claim_video_generation_segment", return_value=generation),
            patch.object(video, "_request_bytes", return_value=(b"segment-video", "video/mp4")),
            patch.object(video, "storage_upload_file", side_effect=["s" * 32, "f" * 32]),
            patch.object(video, "extract_last_video_frame", return_value=b"actual-last-frame") as extract,
            patch.object(video, "_queue_video_continuation", return_value="r2v-prompt") as queue,
            patch.object(video, "advance_video_generation_segment", return_value=True),
            patch.object(video, "reset_generation_progress"),
            patch.object(video, "storage_delete_file"),
        ):
            video._sync_video_output(
                generation,
                self.user.id,
                "completed-segment",
                {"save": {"videos": [{"filename": "segment.mp4", "subfolder": "", "type": "output"}]}},
            )

        extract.assert_called_once_with(content=b"segment-video", filename="segment.mp4")
        queue.assert_called_once_with(generation, self.user.id, "f" * 32, b"actual-last-frame")

    def test_completed_sequence_status_does_not_requery_comfy_history(self) -> None:
        generation = {
            "prompt_id": "root-prompt",
            "mode": "i2v",
            "status": "completed",
            "storage_file_id": "v" * 32,
            "filename": "sequence.mp4",
            "subfolder": "",
            "video_type": "output",
            "fps": 24,
            "length": 240,
            "segment_durations": [10.0, 3.0],
            "segment_index": 1,
        }
        with (
            patch.object(video, "get_video_generation", return_value=generation),
            patch.object(video, "storage_read_url", return_value="/vault/videos/root-prompt/download"),
            patch.object(video, "_request_json") as history,
        ):
            result = video._history_status(generation, self.user.id)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.progress, 100)
        self.assertEqual(result.segment_count, 2)
        history.assert_not_called()

    def test_mode_is_explicit_when_resolving_assets(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        with self.assertRaises(video.HTTPException) as context:
            asyncio.run(
                video._resolve_assets(
                    "fl2v",
                    request,
                    [],
                    self.user,
                )
            )
        self.assertEqual(context.exception.status_code, 422)

    def test_existing_media_is_downloaded_and_not_reuploaded(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move",
            first_frame=video.VideoAsset(kind="image", file_id="a" * 32),
        )
        stored = {"file_id": "a" * 32, "filename": "image.png", "content_type": "image/png", "media_kind": "image"}
        with (
            patch.object(video, "get_reusable_media", return_value=stored),
            patch.object(video, "storage_download_file", return_value=(b"image", "image/png")),
            patch.object(video, "storage_upload_file") as upload,
            patch.object(video, "create_media_asset") as create_media,
        ):
            resolved = asyncio.run(video._resolve_assets("i2v", request, [], self.user))

        self.assertEqual(next(iter(resolved.values())).file_id, "a" * 32)
        upload.assert_not_called()
        create_media.assert_called_once()

    def test_r2v_video_connects_frames_and_audio_components(self) -> None:
        request = video.VideoGenerationRequest(
            prompt="move <Video 1>",
            reference_videos=[video.VideoAsset(kind="video", file_index=0)],
        )
        resolved = {
            "index:0": video._ResolvedAsset(file_id="a" * 32, filename="clip.mp4", content=b"video", media_type="video/mp4", kind="video"),
        }
        with patch.object(video, "_upload_to_comfy", return_value="clip.mp4"):
            prompt, _ = video._build_prompt("r2v", request, resolved)

        self.assertEqual(prompt["300"], {"class_type": "LoadVideo", "inputs": {"file": "clip.mp4"}})
        self.assertEqual(prompt["400"]["inputs"], {"video": ["300", 0]})
        self.assertEqual(prompt["5"]["inputs"]["ref_videos.ref_video_0"], ["400", 0])
        self.assertEqual(prompt["5"]["inputs"]["ref_video_audios.ref_video_audio_0"], ["400", 1])

    def test_audio_input_uses_comfyui_common_upload_route(self) -> None:
        source = video._ResolvedAsset(
            file_id="a" * 32,
            filename="voice.wav",
            content=b"audio",
            media_type="audio/wav",
            kind="audio",
        )

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"name":"voice.wav"}'

        with (
            patch.object(video, "_comfy_url", side_effect=lambda endpoint: f"http://comfy.local{endpoint}"),
            patch.object(video, "urlopen", return_value=Response()) as open_url,
        ):
            result = video._upload_to_comfy({"index:0": source}, video.VideoAsset(kind="audio", file_index=0), "audio")

        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://comfy.local/upload/image")
        self.assertIn(b'name="image"', request.data)
        self.assertNotIn(b'name="audio"', request.data)
        self.assertEqual(result, "voice.wav")

    def test_video_input_has_video_fallback_suffix(self) -> None:
        source = video._ResolvedAsset(
            file_id="a" * 32,
            filename="clip",
            content=b"video",
            media_type="video/mp4",
            kind="video",
        )

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"name":"clip.mp4"}'

        with (
            patch.object(video, "_comfy_url", side_effect=lambda endpoint: f"http://comfy.local{endpoint}"),
            patch.object(video, "urlopen", return_value=Response()) as open_url,
        ):
            video._upload_to_comfy({"index:0": source}, video.VideoAsset(kind="video", file_index=0), "video")

        request = open_url.call_args.args[0]
        self.assertIn(b'filename="local_field_', request.data)
        self.assertIn(b".mp4", request.data)

    def test_video_prompt_pattern_is_language_union_with_digits_and_symbols(self) -> None:
        korean_prompt = "[Shot 1] 장면 0초-3초 <Picture 1> N/A !?"
        self.assertIsNotNone(re.fullmatch(video._video_prompt_pattern(["ko"]), korean_prompt))
        self.assertIsNone(re.fullmatch(video._video_prompt_pattern(["ko"]), " \n"))
        self.assertIsNone(re.fullmatch(video._video_prompt_pattern(["ko"]), f" {korean_prompt}"))
        self.assertIsNone(re.fullmatch(video._video_prompt_pattern(["ko"]), f"{korean_prompt} \n"))
        self.assertIsNone(re.fullmatch(video._video_prompt_pattern(["ko"]), korean_prompt.replace("장면", "scene", 1)))

        mixed_prompt = "[Shot 1] red 빨강 16:9 <Picture 1> N/A !?"
        self.assertIsNotNone(re.fullmatch(video._video_prompt_pattern(["ko", "en"]), mixed_prompt))

        japanese_prompt = "[Shot 1] 動き 0秒-3秒 <Picture 1> N/A !?"
        self.assertIsNotNone(re.fullmatch(video._video_prompt_pattern(["ja"]), japanese_prompt))
        self.assertIsNone(re.fullmatch(video._video_prompt_pattern(["ja"]), japanese_prompt.replace("動き", "move", 1)))

    def test_video_prompt_does_not_revalidate_structured_shot_order(self) -> None:
        plan = {
            "shots": [
                {
                    "start_ms": 3000,
                    "style": "first style",
                    "timeline": "first timeline",
                    "camera": "first camera",
                    "audio": "first audio",
                    "text": "first text",
                },
                {
                    "start_ms": 1000,
                    "style": "second style",
                    "timeline": "second timeline",
                    "camera": "second camera",
                    "audio": "second audio",
                    "text": "second text",
                },
            ],
            "overall_soundscape": "quiet ambience",
            "non_diegetic_music": "N/A",
        }
        payload = video.VideoPromptEnhancementRequest(prompt="move", mode="i2v", duration=5, prompt_output_languages=["en"])
        with patch.object(video, "_request_structured_object", return_value=plan):
            result = video._enhance_video_prompt(payload)
        self.assertIn("[Shot 1] At 00:00:00, first style first camera first audio first text", result.improved_prompt.contents)
        self.assertNotIn("first timeline", result.improved_prompt.contents)
        self.assertIn("[Shot 2] At 00:01.000, second style second timeline second camera second audio second text", result.improved_prompt.contents)
        self.assertNotIn("negative:", result.improved_prompt.contents)

    def test_video_prompt_rejects_missing_structured_timeline(self) -> None:
        plan = {
            "shots": [{"start_ms": 0, "style": "style", "camera": "camera", "audio": "audio", "text": "text"}],
            "overall_soundscape": "quiet ambience",
            "non_diegetic_music": "N/A",
        }
        payload = video.VideoPromptEnhancementRequest(prompt="move", mode="i2v", duration=5, prompt_output_languages=["en"])

        with patch.object(video, "_request_structured_object", return_value=plan), self.assertRaisesRegex(video._VLLMError, "필수 shot field"):
            video._enhance_video_prompt(payload)

    def test_video_prompt_fields_use_fixed_328_character_limit_without_assembled_cap(self) -> None:
        for duration in (1, 5, 10):
            schema = video._video_prompt_fields_schema(["en"], duration)
            shot_schema = schema["properties"]["shots"]
            self.assertEqual(
                [shot_schema["items"]["properties"][field]["maxLength"] for field in video._VIDEO_PROMPT_SHOT_FIELDS],
                [328] * len(video._VIDEO_PROMPT_SHOT_FIELDS),
            )
            self.assertEqual(
                [schema["properties"][field]["maxLength"] for field in video._VIDEO_PROMPT_OVERALL_FIELDS],
                [328] * len(video._VIDEO_PROMPT_OVERALL_FIELDS),
            )

        plan = {
            "shots": [{"start_ms": index, **{field: "x" * 328 for field in video._VIDEO_PROMPT_SHOT_FIELDS}} for index in range(5)],
            **{field: "x" * 328 for field in video._VIDEO_PROMPT_OVERALL_FIELDS},
        }
        payload = video.VideoPromptEnhancementRequest(prompt="move", mode="i2v", duration=5, prompt_output_languages=["en"])
        with patch.object(video, "_request_structured_object", return_value=plan):
            result = video._enhance_video_prompt(payload)

        self.assertGreater(len(result.improved_prompt.contents), 5000)
        with self.assertRaisesRegex(video._VLLMError, "필수 shot field"):
            video._validate_video_prompt_fields(
                {
                    "shots": [{"start_ms": 0, **{field: "x" * (329 if field == "timeline" else 328) for field in video._VIDEO_PROMPT_SHOT_FIELDS}}],
                    **{field: "x" * 328 for field in video._VIDEO_PROMPT_OVERALL_FIELDS},
                }
            )

    def test_submitted_improved_video_prompt_can_exceed_5000_characters(self) -> None:
        improved = "x" * 5001
        request = video.VideoGenerationRequest(
            prompt="move", prompt_enhancement_enabled=True, improved_segment_prompts=[improved]
        )
        enhancement_request = video.VideoPromptEnhancementRequest(
            prompt="move", mode="i2v", previous_segment_prompt=improved
        )

        self.assertEqual(video._submitted_improved_segment_prompts(request, 1), [improved])
        self.assertEqual(enhancement_request.previous_segment_prompt, improved)

    def test_video_prompt_enhancement_uses_selected_languages_and_pattern(self) -> None:
        languages: list[Literal["ko", "en", "ja"]] = ["ko", "en"]
        plan = {
            "shots": [
                {
                    "start_ms": 0,
                    "style": "red 빨강 @image1",
                    "timeline": "0s-5s 움직인다",
                    "camera": "static shot",
                    "audio": "no dialogue",
                    "text": "no visible text",
                }
            ],
            "overall_soundscape": "quiet ambience",
            "non_diegetic_music": "N/A",
        }
        payload = video.VideoPromptEnhancementRequest(
            prompt="사과가 움직인다",
            mode="i2v",
            duration=5,
            prompt_output_languages=languages,
        )
        with patch.object(video, "_request_structured_object", return_value=plan) as request:
            result = video._enhance_video_prompt(payload)

        expected = video._assemble_video_prompt(plan)
        self.assertEqual(result.improved_prompt.contents, expected)
        self.assertEqual(request.call_args.kwargs["temperature"], 0.3)
        self.assertEqual(video._VIDEO_PROMPT_MAX_TOKENS, 1024)
        self.assertEqual(request.call_args.kwargs["max_tokens"], video._VIDEO_PROMPT_MAX_TOKENS)
        self.assertEqual(request.call_args.kwargs["timeout_seconds"], video._VIDEO_PROMPT_TIMEOUT_SECONDS)
        self.assertEqual(request.call_args.kwargs["name"], "video_prompt_shots")
        schema = request.call_args.kwargs["schema"]
        self.assertEqual(set(schema["required"]), {"shots", "overall_soundscape", "non_diegetic_music"})
        self.assertEqual(schema["additionalProperties"], False)
        shots = schema["properties"]["shots"]
        self.assertEqual(shots["items"]["required"], ["start_ms", *video._VIDEO_PROMPT_SHOT_FIELDS])
        self.assertEqual(shots["items"]["additionalProperties"], False)
        self.assertEqual(
            shots["items"]["properties"]["style"]["pattern"],
            video._video_prompt_pattern(languages),
        )
        self.assertNotIn("negative", schema["properties"])
        self.assertIn("Korean, English", request.call_args.kwargs["user_prompt"])

    def test_sequence_enhancement_uses_zero_based_local_timeline_clock(self) -> None:
        plan = {
            "shots": [{"start_ms": 0, **{field: "concrete 0s-1s instruction" for field in video._VIDEO_PROMPT_SHOT_FIELDS}}],
            "overall_soundscape": "quiet room tone",
            "non_diegetic_music": "N/A",
        }
        payload = video.VideoPromptEnhancementRequest(
            prompt="continue the scene",
            segment_prompt="The character leaves the room.",
            mode="r2v",
            duration=1,
            segment_index=1,
            segment_count=2,
            previous_segment_prompt="opening 0s-10s",
            prompt_output_languages=["en"],
        )
        with patch.object(video, "_request_structured_object", return_value=plan) as request:
            video._enhance_video_prompt(payload)

        system_prompt = request.call_args.kwargs["system_prompt"]
        user_prompt = request.call_args.kwargs["user_prompt"]
        self.assertIn("The global style and background apply to every sequence segment", system_prompt)
        self.assertIn("never repeat its timeline actions", system_prompt)
        self.assertNotIn("negative", system_prompt)
        self.assertIn("start_ms is 0; later start_ms values are increasing cut times in the supplied local segment", system_prompt)
        self.assertIn("<global_style_and_background>\ncontinue the scene\n</global_style_and_background>", user_prompt)
        self.assertIn("<current_segment_instruction>\nThe character leaves the room.\n</current_segment_instruction>", user_prompt)
        self.assertIn("<duration_seconds>\n1\n</duration_seconds>", user_prompt)
        self.assertIn("<sequence_segment>\n2/2\n</sequence_segment>", user_prompt)
        self.assertIn("<timeline_clock>\n0s to 1s", user_prompt)

    def test_enabled_video_enhancement_forwards_user_edited_prompt_to_workflow(self) -> None:
        improved = "user edited freeform prompt with no section format"
        request = video.VideoGenerationRequest(
            prompt="move",
            prompt_enhancement_enabled=True,
            improved_prompt=improved,
            prompt_output_languages=["en"],
            first_frame=video.VideoAsset(kind="image", file_index=0),
        )
        effective = video._effective_video_prompt("i2v", request)
        self.assertIn("<Picture 1>: start-image reference", effective)
        self.assertIn(improved, effective)

    def test_duplicate_video_prompt_languages_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            video.VideoGenerationRequest(prompt="move", prompt_output_languages=["en", "en"])


if __name__ == "__main__":
    unittest.main()
