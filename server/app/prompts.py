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
    "Rewrite the user's idea as precise shot data while preserving its intent. "
    "Return exactly one JSON object with shots, overall_soundscape, and non_diegetic_music. "
    "Each shots item must contain start_ms, style, timeline, camera, audio, and text. "
    "Do not put section headers, shot headings, or timestamps inside string field values. "
    "The first start_ms is 0; later start_ms values are increasing cut times in the supplied local segment. "
    "Use only as many shots as needed. "
    "Style must define the current shot's medium, texture, palette, era, and visual identity. "
    "The global style and background apply to every sequence segment. "
    "The current segment instruction defines only this segment's actions; do not add actions from another segment. "
    "Timeline must define concrete visible actions for the current shot. "
    "For a sequence segment, never use global sequence timestamps or plan beyond the supplied duration. "
    "For segment 2 or later, <Picture 1> is the actual final frame from the preceding segment; preserve continuity from it. "
    "Use the previous segment prompt only for visual continuity; never repeat its timeline actions. "
    "Camera must state exact movement or explicitly reject movement and cuts. "
    "Audio contains only shot-synchronous dialogue, singing, diegetic music, and sound actions. "
    "Text must spell every readable on-screen string exactly and forbid invented text when needed. "
    "overall_soundscape summarizes ambience and physical sounds across the complete local segment. "
    "non_diegetic_music describes audience-only music or N/A. "
    "Every string value is one concise sentence and stops after its required information. "
    "Use MiniMax H3 reference markers exactly as <Picture 1>, <Video 1>, and <Audio 1>. "
    "Convert any [Image1], [Video1], [Audio1], @image1, @video1, or @audio1 style marker to the exact MiniMax H3 form. "
    "Use direct visual actions instead of vague adjectives. "
    "Do not add explanations, markdown fences, or extra JSON fields. "
    "Write using only the selected output languages, while always preserving digits and special symbols."
)

VIDEO_PROMPT_ENHANCEMENT_USER_PROMPT = (
    "<global_style_and_background>\n{prompt}\n</global_style_and_background>\n"
    "<current_segment_instruction>\n{segment_prompt}\n</current_segment_instruction>\n"
    "<mode>\n{mode}\n</mode>\n"
    "<duration_seconds>\n{duration}\n</duration_seconds>\n"
    "<timeline_clock>\n0s to {duration}s in this segment only; never use global sequence timestamps.\n</timeline_clock>\n"
    "<sequence_segment>\n{segment_number}/{segment_count}\n</sequence_segment>\n"
    "<previous_segment_prompt>\n{previous_segment_prompt}\n</previous_segment_prompt>\n"
    "<output_languages>\n{languages}\n</output_languages>\n"
    "<required_fields>\nshots[].start_ms, shots[].style, shots[].timeline, shots[].camera, shots[].audio, shots[].text, overall_soundscape, non_diegetic_music\n</required_fields>"
)
