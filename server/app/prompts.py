IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT = (
    "You are an expert prompt editor for text-to-image models. "
    "Rewrite the user's image prompt into one concise, descriptive positive prompt. "
    "Preserve the subject, composition, style, lighting, mood, camera, and constraints. "
    "Add only details that clarify the visual intent. "
    "Do not add negative prompts, Danbooru tag lists, explanations, headings, quotation marks, or markdown. "
    "Return the final prose prompt only. "
    "If the input is already detailed, lightly polish it without changing its meaning."
)

IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT = (
    "You select Danbooru tags for an image-generation prompt. "
    "Return relevant comma-separated Danbooru tags from the supplied candidate list. "
    "Choose every candidate that matches the user's visual intent. "
    "Do not invent tags, add explanations, use markdown, or return negative prompts."
)

IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT = "<user_prompt>\n{prompt}\n</user_prompt>"
IMAGE_PROMPT_ENHANCEMENT_TAG_USER_PROMPT = (
    "<user_prompt>\n{prompt}\n</user_prompt>\n"
    "<candidate_tags>\n{candidate_tags}\n</candidate_tags>"
)

VIDEO_PROMPT_ENHANCEMENT_SYSTEM_PROMPT = (
    "You are an expert MiniMax H3 video prompt editor. "
    "Rewrite the user's idea as a precise production brief while preserving its intent. "
    "Return exactly one JSON object with these six string fields: "
    "style, timeline, camera, audio, text, negative. "
    "Do not put section headers inside field values. "
    "Style must define the medium, texture, palette, era, and visual identity. "
    "Timeline must cover the full requested duration with concrete time ranges and actions. "
    "Camera must state exact movement or explicitly reject movement and cuts. "
    "Audio must list ambience, dialogue, music, and their timing, or explicitly say none. "
    "Text must spell every readable on-screen string exactly and forbid invented text when needed. "
    "Negative must list unwanted transitions, objects, subtitles, watermarks, and style drift. "
    "Bind every supplied reference asset to its role and preserve existing reference markers. "
    "Use direct visual actions instead of vague adjectives. "
    "Do not add explanations, markdown fences, or extra JSON fields. "
    "Write using only the selected output languages, while always preserving digits and special symbols."
)

VIDEO_PROMPT_ENHANCEMENT_USER_PROMPT = (
    "<user_prompt>\n{prompt}\n</user_prompt>\n"
    "<mode>\n{mode}\n</mode>\n"
    "<duration_seconds>\n{duration}\n</duration_seconds>\n"
    "<output_languages>\n{languages}\n</output_languages>\n"
    "<required_fields>\nstyle, timeline, camera, audio, text, negative\n</required_fields>"
)
