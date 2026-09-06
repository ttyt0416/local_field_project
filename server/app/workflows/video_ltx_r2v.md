# LTX R2V workflow

`video_ltx_r2v.json` is the LTX 2.5 image-guide reference graph. `video.py` appends one ordered guide chain per selected image and spaces guide frames across the requested output. LTX R2V does not accept reference video or audio. Selected live `LTX/` LoRAs are model-only chains after the UNET loader.

`0` is the direct `easy cleanGpuUsed` start output node. `video.py` refreshes its `is_changed` value for every request, including repeated fixed-seed runs.
