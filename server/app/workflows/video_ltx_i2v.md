# LTX I2V workflow

`video_ltx_i2v.json` is the LTX 2.5 image-to-video graph. `video.py` replaces its prompt, seed, frame rate, dimensions, frame count, and temporary first-frame input at request time. I2V requires 64-pixel multiples. `upscale=true` keeps the latent spatial-upscale and second denoise pass; `upscale=false` removes that branch and decodes the first-pass video/audio latent at half the requested resolution. Selected live `LTX/` LoRAs are chained with `LoraLoaderModelOnly` between the UNET loader and every model consumer; MiniMax and image LoRAs are never injected.
