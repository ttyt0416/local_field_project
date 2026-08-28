# Storage signed URL과 파일 수명

Local Field 서버는 브라우저에 Storage 서비스 토큰을 전달하지 않는다. 사용자 소유권을 확인한 뒤 짧은 만료시간의 signed read URL을 발급하며, `(file_id, owner_id, expires_in)` 조합으로 서버 메모리에 캐시한다. 파일 삭제가 성공하거나 이미 없는 경우 해당 소유자의 캐시를 무효화한다.

동영상 생성의 새 이미지·오디오 입력은 생성 요청 시점에만 업로드한다. 기존 파일은 소유권 검증 후 다운로드해 ComfyUI 입력으로 전달하고 재업로드하지 않는다. 생성 영상 결과는 ComfyUI history에서 읽어 Storage에 저장한다.
