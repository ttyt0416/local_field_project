# LTX FL2V workflow

`video_ltx_fl2v.json` is the LTX 2.5 first-and-last-frame graph. `video.py` supplies temporary first/last inputs and request dimensions to both DynamicCombo resize nodes. Selected live `LTX/` LoRAs are model-only chains after the UNET loader. The graph does not use MiniMax adapters.
