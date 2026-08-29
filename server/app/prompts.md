# Prompt enhancement

Image prompt enhancement keeps its existing structured output contract. Video prompt enhancement uses the same vLLM request helper with `temperature=0.8`, but asks for one JSON object containing exactly the six string fields `style`, `timeline`, `camera`, `audio`, `text`, and `negative`. The server validates each field, then assembles the final labeled prompt. Each field supplies a dynamic character pattern for the selected `ko`, `en`, and `ja` output languages. Digits, ASCII punctuation, spaces, and line breaks are always part of the allowed set. vLLM output requests allow up to 10 minutes; the image and video enhancement UI requests use the same 10-minute limit.

The video system prompt follows the AtlasCloud MiniMax H3 guide before the Pixo guide: `Style`, `Timeline`, `Camera`, `Audio`, `Text`, and `Negative` are required in that order. Reference roles are added by the server after enhancement so the labels match the actual I2V, FL2V, or R2V inputs.

References:

- https://www.atlascloud.ai/ko/blog/tips/minimax-h3-prompt-guide
- https://pixo.video/ko/blog/minimax-h3-prompt-guide