# YuE2 API workflow

Derived from the official `Comfy-Org/workflow_templates/templates/audio_yue2_text2music.json`. Native checkpoint → optional ABC plan → music semantics → duration-sized latent → 32-step dpm_2/sgm_uniform → audio VAE → FLAC. Node 2 is removed when planning is off or a user score is supplied. Node 3 owns style, lyrics, score, mode and maximum duration; nodes 2, 3 and 6 share the request seed. SaveAudioAdvanced uses the native flat dynamic-combo `format=flac` prompt input.
