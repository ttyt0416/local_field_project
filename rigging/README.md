# SkinTokens 로컬 실행

공식 코드와 두 checkpoint는 `/home/yoon/dev/SkinTokens`에 설치했다. 설치 commit과 checkpoint SHA-256은 `installation.json`에 기록했다. 모델 용량은 약 1.6 GB다.

이 장비는 NVIDIA GB10·Linux ARM64다. 공식 bpy wheel을 사용할 수 없어 이 폴더의 GLB 입출력 adapter와 PyTorch SDPA 연결을 사용한다. 모델과 upstream 소스는 그대로다. 전용 `.venv`는 기존 `/home/yoon/comfyui-env/lib/python3.12/site-packages`를 `.pth`로 읽으며 필요한 패키지만 전용 venv에 추가한다. 기존 ComfyUI 환경에는 설치하거나 수정하지 않는다. 복원 시 해당 GPU PyTorch 경로를 새 venv의 site-packages에 `.pth`로 추가하고 이 폴더의 requirements.txt를 설치한다. 모델 다운로드는 upstream의 `python download.py --model`을 사용한다.

현재 worker는 다음 사용자 transient service로 시작했다. 운영 web/server container는 이 작업에서 rebuild하거나 재시작하지 않았다.

```bash
systemd-run --user --unit=local-field-rigging \
  --property=Restart=on-failure \
  --property=WorkingDirectory=/home/yoon/dev/local_field_project/rigging \
  /usr/bin/python3 /home/yoon/dev/local_field_project/rigging/worker.py
systemctl --user status local-field-rigging
journalctl --user -u local-field-rigging
```

transient unit은 재부팅 후 다시 시작해야 한다. 지속적인 부팅 자동 시작은 별도의 운영 설정이다. 수동 foreground 실행은 `python3 rigging/worker.py`다. service와 동시에 실행하지 않는다.

worker는 8190에서 token 인증을 요구한다. `.runtime/token`은 시작 시 0600으로 생성되며 UI나 log에 노출하지 않는다. Compose 설정은 이 파일을 backend에 read-only mount하고 `RIGGING_URL=http://host.docker.internal:8190`으로 연결한다. worker를 먼저 실행해 token 파일을 만든 뒤 web/server 변경을 기존 배포 절차로 반영한다. startup DB migration은 기존 3D row를 mesh로 유지하며 rigging 필드만 추가한다.

기능은 GLB 업로드/보관함 MESH → SkinTokens skeleton·skin 생성 → 원본 색상·재질·크기를 보존한 GLB다. 기존 rig·morph·압축 확장·외부 리소스 참조 파일은 거부한다. 리깅 결과에는 동작 animation이 포함되지 않는다. 화면 viewer는 모델의 회전·확대를 지원하고 bone 편집 기능은 제공하지 않는다.

검증: 공식 giraffe.glb로 직접 추론(Beam 1)과 worker 기본 설정(Beam 10) 모두 성공했다. 직접 추론 결과는 32 joints·14,807 input vertices였고 worker 결과는 약 6.7 MB다. token 인증 거부, queued job 취소, 결과 다운로드와 ack를 확인했다. `test_glb.py`는 변환 인스턴스·재질·vertex color·inverse bind·정규화 가중치를 확인한다.

```bash
/home/yoon/dev/SkinTokens/.venv/bin/python -m unittest discover -s rigging -p test_glb.py
```

upstream 저장소와 모델 카드는 MIT를 표시한다. Michelangelo 하위 코드에는 GPL 관련 경계가 있으므로 원본 LICENSE 및 upstream issue #9의 설명을 보존하고 배포 범위를 검토한다. 이 작업은 로컬 설치이며 외부 배포나 재라이선스를 수행하지 않았다.
