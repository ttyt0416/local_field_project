# TRELLIS.2 3D generation API

`POST /generation/3d`는 단일 이미지와 `preview`·`standard`·`high` preset을 받아 현재 host ComfyUI의 official core TRELLIS.2 workflow를 queue에 제출한다. TRELLIS.2 native contract인 image-to-3D만 지원하며 text-to-3D, multi-view, rigging, animation은 이 API 범위가 아니다.

요청은 multipart `payload` JSON과 선택적인 `files` 한 개다. `source.file_index=0`이면 submit 시에만 새 이미지를 Storage와 `media_assets`에 저장한다. `source.file_id`이면 현재 사용자의 기존 이미지 ownership을 확인하고 재사용한다. `seed`, `remove_background`, `padding`을 지원하며 stage sampler·CFG는 workflow 상수로 유지한다. Seed는 브라우저 JSON number 반올림을 막기 위해 `0..2^53-1` 범위다.

`GET /generation/3d/options`는 static workflow의 node type과 필요한 INT8 TRELLIS.2, DINOv3 vision, shape/texture VAE, BiRefNet filename이 live ComfyUI `/object_info`에 노출되는지 확인한다. classic combo와 Comfy `COMBO.options` schema를 모두 처리한다.

status·SSE stage는 `queued`, `background_cleanup`, `structure`, `shape`, `texture`, `mesh`, `storage`, `completed` 순서다. global diffusion percentage를 stage 전체 진행률로 오인하지 않으며 Comfy KSampler가 제공한 값만 `progress`로 전달한다. cancel은 공통 ComfyUI `POST /api/jobs/{prompt_id}/cancel`을 사용하며, target job이 실행 중이면 interrupt하고 pending이면 dequeue한다.

완료 history의 `outputs[*].3d`에서 `.glb`만 수집한다. `/view` 바이트의 GLB magic `glTF`를 확인한 뒤 `model/gltf-binary` MIME으로 Storage에 업로드하고 DB row를 완료한다. GLB가 없거나 magic이 다르면 성공으로 기록하지 않는다. 결과 mesh가 watertight 또는 3D printing-ready임을 보장하지 않는다.
