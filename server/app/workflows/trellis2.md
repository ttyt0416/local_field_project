# TRELLIS.2 ComfyUI API workflow

`trellis2.json`은 Comfy-Org official Pixal3D + TRELLIS.2 UI template에서 TRELLIS.2 dependency branch만 추출한 38-node API graph다. Pixal3D, note, preview output은 제거하고 최종 textured mesh를 core `SaveGLB` 하나에 연결한다.

Runtime binding node:

- `122`: Comfy input image filename
- `248`: background removal switch
- `312`: image padding
- `3`, `12`, `18`, `23`: 공통 user seed
- `94`: TRELLIS target resolution
- `186`: target face count
- `288`: texture resolution
- `241`: remesh resolution
- `224`, `233`: normal·ambient-occlusion bake resolution
- `900`: unique GLB filename prefix

Preview는 `1024 / 150k faces / 1024 texture`, Standard는 `1024 / 350k / 2048`, High는 `1536 / 700k / 4096`을 사용한다. 이 값은 UI의 복잡한 stage parameter 대신 제공하는 bounded preset이며 실제 host benchmark 뒤 조정할 수 있다.

Workflow는 ComfyUI core node만 사용한다. 별도 TRELLIS custom node, `nvdiffrast`, `nvdiffrec`, standalone Microsoft exporter를 runtime dependency로 추가하지 않는다.
