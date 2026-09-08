# Music generation API

`music.py`는 shared local ComfyUI의 native MiniMax-Music3 node로 text-to-music generation을 실행한다.

- `GET /generation/music/options`: required node, exact model filename, Storage readiness를 확인한다.
- `POST /generation/music`: description, optional lyrics, 10-300 second limit, optional seed를 official 30-step workflow에 넣고 `202`를 반환한다. 빈 lyrics는 instrumental generation이다.
- `GET /generation/music/latest`: reload 뒤 latest result 또는 active job을 복구한다.
- `GET /generation/music/{prompt_id}`와 `/events`: DB snapshot, progress, queue position, terminal output을 반환한다.
- `POST /generation/music/{prompt_id}/cancel`: 해당 ComfyUI prompt만 native cancel한다.
- 완료된 FLAC, WAV, MP3, OGG output은 Storage에 저장하고 signed URL만 client에 반환한다.

Runtime model은 `Comfy-Org/MiniMax-Music-3` revision `6baad88896848433857c170ba4f05d2ea9d5f218`의 FP16 DiT, pruned INT8 text encoder, DAV file을 사용한다. Source model은 `MiniMaxAI/MiniMax-Music3` revision `fbdf52fbaaca799592917417eb05f1899f1255ec`에 고정한다.
