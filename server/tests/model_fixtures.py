def model_object_info():
    def node(**inputs):
        return {"input": {"required": {key: [values] for key, values in inputs.items()}}}
    return {
        "UNETLoader": node(unet_name=["MiniMaxH3/custom/model.safetensors", "Qwen/custom.safetensors", "Anima/custom.safetensors", "MOSS/custom.safetensors", "TripoSplat/custom.safetensors"]),
        "CLIPLoader": node(clip_name=["Anima/renamed.safetensors", "MOSS/renamed.safetensors", "Qwen/Encoder/renamed.safetensors", "Qwen/PromptEnhancer/renamed.safetensors", "MiniMaxH3/renamed.safetensors"], type=["moss_image", "minimax", "qwen_image"]),
        "VAELoader": node(vae_name=["Anima/renamed.safetensors", "MOSS/renamed.safetensors", "Qwen/renamed.safetensors", "MiniMaxH3/Video/renamed.safetensors", "MiniMaxH3/Audio/renamed.safetensors", "TripoSplat/Image/renamed.safetensors", "TripoSplat/Splat/renamed.safetensors"]),
        "CheckpointLoaderSimple": node(ckpt_name=["YuE2/renamed.safetensors"]),
        "CLIPVisionLoader": node(clip_name=["TripoSplat/renamed.safetensors"]),
        "LoadBackgroundRemovalModel": node(bg_removal_name=["TripoSplat/renamed.safetensors"]),
        "MiniMaxH3PDDAccApply": node(pdd_file=["MiniMaxH3/Ref2VA/renamed.safetensors"]),
        "MinimaxH3LatentUpscaler3D": node(model_name=["MiniMaxH3/renamed.safetensors"]),
        "KSampler": node(sampler_name=["euler", "er_sde"], scheduler=["simple", "sgm_uniform"]),
        "KSamplerSelect": node(sampler_name=["euler", "res_multistep"]),
        "BasicScheduler": node(scheduler=["simple", "normal"]),
        "LoraLoaderModelOnly": node(lora_name=[]),
    }
