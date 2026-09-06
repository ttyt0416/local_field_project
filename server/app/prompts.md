# Prompt enhancement

Image prompt enhancement는 기존 structured output contract and 10-minute request limit를 유지한다. Video prompt enhancement는 same vLLM request helper에서 `temperature=0.3`, `max_tokens=1024`, `timeout_seconds=120`으로 one strict JSON object를 요청한다. object는 `shots`, `overall_soundscape`, `non_diegetic_music`를 포함하고 every `shots[]` object는 `start_ms`, `style`, `timeline`, `camera`, `audio`, `text`를 가진다. 모든 video text field는 independent 1~328 chars이며 selected `ko`, `en`, `ja` output language, digits, ASCII punctuation, exact server-owned structural token만 허용한다. field는 visible content로 시작·끝나서 whitespace-only or trailing-whitespace output을 허용하지 않는다. server는 required nested field와 length를 typed validation한 뒤 final prompt를 조립하며 assembled result에는 aggregate 5000-char cap이 없다.

The video system prompt returns only shot data; server owns `[Shot N]`, `At MM:SS.mmm`, and final section order. Reference roles are added by the server after enhancement so the labels match the actual I2V, FL2V, or R2V inputs. Long video enhancement sends the one user-entered overall prompt for every duration-derived segment with segment number, segment duration, and prior scene context. vLLM distributes the overall intent across segments while every shot uses its own local segment clock, never a global sequence timestamp. Segment 2 onward is R2V and `<Picture 1>` means the actual final frame from the prior generated segment. vLLM returns reviewable proposals only; it never writes user scene prompts.

References:

- https://www.atlascloud.ai/ko/blog/tips/minimax-h3-prompt-guide
- https://pixo.video/ko/blog/minimax-h3-prompt-guide