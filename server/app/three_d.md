# TripoSplat 3D API

완료된 MESH·RIGGING 상태와 SSE의 모델 URL은 `vault/3d/{generation_id}/model` 인증 경로를 반환한다. 뷰어가 인증된 파일 바이트를 받아 표시하므로 Storage 공개 URL의 CORS나 만료시간에 의존하지 않는다.

`GET /generation/3d/options` checks native nodes, all five required model filenames and Storage. The model is local TripoSplat, with no Tripo API key or cloud inference. `POST /generation/3d` accepts the existing multipart source (new image or owner-checked Storage image), preset, seed and background removal. It uploads inputs only after readiness passes, submits a ComfyUI prompt, and creates the existing generation DB row.

Presets: preview = 12 steps / 32,768 Gaussians / mesh resolution 192; standard = 20 / 131,072 / 256; high = 30 / 262,144 / 384. The official preprocessing fixes image size at 1024 and crop padding at 1.2; the obsolete adjustable padding form is removed and DB padding records 1.2. Both diffusion and Gaussian decode use the same seed. Disabling background removal uses the input alpha (opaque images use the full image).

The output path is native Gaussian-to-coloured-mesh extraction followed by SaveGLB. GLB conversion is experimental, uses vertex colours and can lose thin or small geometry; it does not guarantee UV textures, watertightness, rigging or print-ready meshes. Stage mapping covers input/background, conditioning/sampling, decode and mesh export. Existing GLB validation, Storage upload, status, SSE, cancel and Vault remain. Terminal DB results do not depend on retained ComfyUI history.

Model: `VAST-AI/TripoSplat` revision `56a96e603204ec410c4da60c13ea4fa09a2169a9`. Reuses shared BiRefNet; adds only the diffusion model, ViT-H vision encoder, Flux2 VAE and splat decoder. Shared services and upstream ComfyUI core are unchanged.

3D API는 generation_mode=rigging row의 상태 조회·SSE·취소를 rigging.py에 위임한다. MESH의 TripoSplat graph는 변경하지 않는다. 리깅 status에는 generation_mode와 nullable message를 포함하고, ComfyUI queue 조회를 사용하지 않는다.
