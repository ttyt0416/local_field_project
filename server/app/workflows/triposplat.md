# TripoSplat API workflow

Derived from the official `Comfy-Org/workflow_templates/templates/3d_triposplat_image_to_gaussian_splat.json`, retaining only the experimental coloured GLB mesh branch. Nodes 1–6 load an image and choose BiRefNet or input alpha, then preprocess at 1024. Nodes 7–11 encode and sample; nodes 12–13 decode Gaussians; 14 extracts a coloured mesh and 15 exports GLB. No API nodes, preview render, video branch, extra custom node or background model download is used.

All five model loader inputs use folder selectors. The server resolves the diffusion, vision, image VAE, splat VAE and background-removal roles from their TripoSplat subfolders before submission, without filename matching.
