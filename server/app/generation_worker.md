# Generation worker

`generation_worker.py`는 서버 startup 시 실행되는 background reconciler다. DB에서 `queued` 또는 `processing` 상태인 이미지·동영상·3D generation을 조회하고, 각 작업의 ComfyUI history를 확인한다.

- 이미지 완료: ComfyUI output을 읽어 Storage에 저장하고 `image_generations`를 완료 상태로 갱신한다.
- 동영상 완료: ComfyUI video output을 읽어 Storage에 저장하고 `video_generations`를 완료 상태로 갱신한다.
- 3D 완료: ComfyUI `outputs[*].3d`의 GLB를 검증해 Storage에 저장하고 `three_d_generations`와 stage를 갱신한다.
- ComfyUI가 일시적으로 unavailable이면 해당 작업을 실패로 바꾸지 않고 다음 주기에 재시도한다.
- 서버가 재시작되어도 DB에 남은 active generation을 다시 발견하므로 브라우저 생명주기와 무관하게 처리된다.
- 상태 DB commit 뒤 generation event broker에 변경을 publish해 연결된 SSE client에 push한다.
- 각 reconcile cycle은 active generation의 elapsed time을 DB에 저장하고 SSE snapshot에도 `created_at`과 `elapsed_seconds`를 포함한다. terminal 상태에서는 완료·실패 시각 기준의 고정 소요 시간이 보관된다.
- shutdown 시 stop event를 설정하고 worker task가 종료될 때까지 기다린다.

프런트는 이미지와 동영상 모두 generation별 SSE endpoint를 구독한다. SSE는 연결 시 DB snapshot을 한 번 전송한 뒤 worker가 publish한 상태·완료·실패 이벤트를 받으며, 연결이 끊기면 재연결 후 DB snapshot으로 누락된 상태를 보완한다. 실제 inference와 video queue 실행은 이 계약 테스트에서 호출하지 않는다.
