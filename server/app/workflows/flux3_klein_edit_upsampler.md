# FLUX 3 Klein 편집 프롬프트 확장

`flux3_klein_edit_upsampler.txt`는 Comfy-Org 공식 `image_flux3_klein_distilled_image_edit.json`의 PrimitiveStringMultiline node 48 system prompt다. 원본과 수정 지시를 함께 TextGenerate에 전달하며 결과 문자열을 diffusion text encoder로 보낸다.

출처: https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux3_klein_distilled_image_edit.json
모델: https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy/tree/feef60b0aaf63a4773ace96636ebbcf43b881312
