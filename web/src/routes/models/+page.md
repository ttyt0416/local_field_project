# civitai 다운로드 화면

메뉴와 화면 이름은 정확히 `civitai 다운로드`다. 체크포인트, LoRA, 텍스트 인코더, VAE, 임베딩 중 하나를 선택하고 Civitai 모델 version ID 또는 링크를 조회한 뒤 파일을 선택한다.

브라우저는 파일을 직접 받지 않는다. `POST /models/civitai/download`로 서버 download job만 생성하고, 상태는 `GET /models/downloads`로 확인한다. 실패한 job은 `다시 시도`로 재요청할 수 있다. 서버 worker가 ComfyUI 모델 폴더에 저장하므로 route를 떠나거나 브라우저를 닫아도 다운로드가 계속된다.

설치된 모델은 `GET /models/installed`에서 읽어 표시한다. 각 모델의 삭제 버튼은 확인 후 `DELETE /models/installed/{model_type}/{filename}`을 호출하며, 서버가 허용된 모델 폴더 내부의 파일만 삭제한다. Civitai token과 download URL은 frontend에 노출하지 않는다.
