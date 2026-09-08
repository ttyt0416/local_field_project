# MiniMax-Music3 workflow

`music_t2m.json`은 ComfyUI official MiniMax-Music3 template을 API prompt 형식으로 줄인 local text-to-music graph다.

- FP16 DiT: `minimax_music3_dit_fp16.safetensors`
- text encoder: `minimax_music3_text_encoder_pruned_int8_convrot.safetensors`
- DAV: `minimax_music3_dav.safetensors`
- sampler: 30 steps, Euler, simple scheduler, CFG 1.7
- output: core `SaveAudio`

Request마다 caption, lyrics, max duration, seed, unique filename prefix만 바꾼다. Tiled decode와 advanced output options는 exposed UI requirement가 생길 때 추가한다.
