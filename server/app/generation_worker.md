# Generation worker

`generation_worker.py`는 서버 startup 시 실행되는 background reconciler다. DB에서 `queued` 또는 `processing` 상태인 이미지·동영상 generation을 조회하고, 각 작업의 ComfyUI history를 확인한다.

- 이미지 완료: ComfyUI output을 읽어 Storage에 저장하고 `image_generations`를 완료 상태로 갱신한다.
- 동영상 완료: ComfyUI video output을 읽어 Storage에 저장하고 `video_generations`를 완료 상태로 갱신한다.
- ComfyUI가 일시적으로 unavailable이면 해당 작업을 실패로 바꾸지 않고 다음 주기에 재시도한다.
- 서버가 재시작되어도 DB에 남은 active generation을 다시 발견하므로 브라우저 생명주기와 무관하게 처리된다.
- shutdown 시 stop event를 설정하고 worker task가 종료될 때까지 기다린다.

프런트는 이미지와 동영상 모두 generation별 SSE endpoint를 구독한다. SSE는 서버 DB 상태가 `completed` 또는 `failed`로 바뀌는 시점에 terminal event를 전달하며, 연결이 끊기면 제한된 횟수로 재연결한다. 실제 inference와 video queue 실행은 이 계약 테스트에서 호출하지 않는다.
