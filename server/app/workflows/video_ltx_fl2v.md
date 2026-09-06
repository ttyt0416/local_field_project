# LTX FL2V workflow

`video_ltx_fl2v.json` is the LTX 2.5 first-and-last-frame graph. `video.py` supplies temporary first/last inputs and request dimensions to both DynamicCombo resize nodes. Selected live `LTX/` LoRAs are model-only chains after the UNET loader. The graph does not use MiniMax adapters.

`0` is the direct `easy cleanGpuUsed` start output node. `video.py` refreshes its `is_changed` value for every request, including repeated fixed-seed runs.
