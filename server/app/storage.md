# Storage signed URL과 파일 수명

Local Field 서버는 브라우저에 Storage 서비스 토큰을 전달하지 않는다. 사용자 소유권을 확인한 뒤 짧은 만료시간의 signed read URL을 발급하며, `(file_id, owner_id, expires_in)` 조합으로 서버 메모리에 캐시한다. 파일 삭제가 성공하거나 이미 없는 경우 해당 소유자의 캐시를 무효화한다. 브라우저용 URL은 Storage의 public URL을 사용하지만, 서버가 입력 파일을 다운로드할 때는 signed URL의 path·query만 유지하고 `STORAGE_URL`의 내부 host로 요청해 Cloudflare public edge를 우회한다.

동영상 생성의 새 이미지·동영상·오디오 입력은 생성 요청 시점에만 업로드한다. 기존 파일은 소유권 검증 후 다운로드해 ComfyUI 입력으로 전달하고 재업로드하지 않는다. ComfyUI 입력 파일은 0.34.2의 공통 `/upload/image` 입력 저장 route를 사용하며, `LoadAudio`도 이 입력 폴더에서 오디오·동영상 확장자를 읽는다. 생성 영상 결과는 ComfyUI history에서 읽어 Storage에 저장한다. 이미 generation 결과였던 파일을 input으로 재사용하면 `media_assets`에 사용 기록을 남기므로 generation 결과를 삭제해도 재사용 파일은 보존한다.

파일 용량은 업로드 시 `media_assets.size`에 기록하고, 생성·편집 결과는 저장 bytes를 generation `size_bytes`에 기록한다. 이전 generation처럼 기록이 없는 파일은 상세 조회에서 signed URL의 HEAD 또는 1-byte range metadata로 보완하며, Storage 토큰은 브라우저에 노출하지 않는다.
