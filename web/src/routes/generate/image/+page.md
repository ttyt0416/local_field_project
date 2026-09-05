# T2I 결과 표시

`/generate/image`는 하나의 T2I route다. negative prompt는 빈 값으로 시작한다. 파라미터 설정은 긍정·부정 본문 위에 각각 `긍정 프롬프트 Prefix`, `부정 프롬프트 Prefix` textarea를 제공한다. prefix는 preset에서 본문과 independent field로 저장·복원하며 server는 prefix와 본문을 합성한 final prompt를 생성·Vault에 저장한다. LoRA 선택 개수에는 제한이 없다. 페이지 family tab으로 Anima, Illustrious, Krea2를 전환하며 query family에 맞는 model·LoRA options와 backend loader를 사용한다. Anima는 Diffusion Model, Illustrious는 full checkpoint, Krea2는 installed Turbo NVFP4 UNET와 Krea2 Qwen3VL encoder·Qwen Image VAE의 split model stack을 사용한다. Krea2는 official Turbo defaults인 Euler / Simple / CFG 1 / 8 steps로 시작하고 native workflow의 zero negative conditioning 때문에 negative prompt control과 negative prefix control을 표시하지 않는다. Krea2 T2I는 `t2i_krea2` preset namespace를 사용한다.

checkpoint와 LoRA selector는 ComfyUI relative model filename의 folder hierarchy를 button으로 표시한다. `전체`는 family scope 내 전체 model을, folder button은 해당 folder 및 하위 model만 표시한다. 하위 folder 선택 시 `전체` 바로 다음의 `바로 위 폴더` button으로 한 level씩 되돌아간다. 선택 값은 backend가 family-scoped option 목록 안에 있는지 다시 검증한다.

프리셋은 Anima `t2i_anima`, Illustrious `t2i_illustrious` namespace를 사용한다. 서로 다른 family/mode preset은 불러오거나 저장하지 않는다. `프롬프트 개선`은 Anima에서는 기존 Danbooru tags와 자연어 개선을 유지하고, Illustrious에서는 검증된 comma-separated Danbooru tags만 반환한다.
