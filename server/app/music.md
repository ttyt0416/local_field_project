# YuE2 music API

`GET /generation/music/options` checks native YuE2 nodes, `yue2_3b_int8_convrot.safetensors` and Storage. Unavailable dependencies return options with `service_available=false`; submit returns HTTP 503 before queue or generation DB writes.

`POST /generation/music` accepts style in `description`, optional section-tagged `lyrics`, `duration_seconds` (10–900, default 120), seed, `planning_mode` (`full`, `melody`, `off`; default `full`) and optional `abc` (up to 20,000 characters). `full` plans melody and chords, `melody` plans melody only, `off` skips ABC. A supplied score skips ABC generation. The generated semantic duration, rather than the requested ceiling, sizes the acoustic latent. Sampling follows the official 32-step `dpm_2` / `sgm_uniform` template. Output is FLAC. Existing status, latest, SSE, cancel, audio validation and Storage behavior remain.

The vLLM description enhancer writes concise YuE2 Style; the lyrics enhancer writes singable words and section tags, separating musical instructions from lyrics and ABC. Selected language, strict JSON schema and provider error auditing remain. Requested duration is an upper bound; prompt context and end tokens can shorten output.

Model: `Comfy-Org/YuE2` revision `2f76ca75e6ee094169de899cc7fc99d6887e2196`. Native checkpoint contains the text, acoustic and audio decoder weights. SheetSage2 is only needed for audio-cover transcription, which this text-to-music screen does not implement.

Music vLLM structured output: Style is `{language, genre, vocals, tempo_bpm, instruments, mood, production}`; Lyrics is `{sections: [{kind, lines}]}`. Extra keys, wrong types, tags/newlines in raw fields and unselected languages are rejected in server validation. The server orders Style fields, adds BPM, generates enum section tags and joins lyric lines/sections. The public response remains `{contents}` for editable UI proposals. Invalid provider output is attached to the existing error audit; no free-form fallback is used.
