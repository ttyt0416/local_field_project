# I2I

`/generate/image-to-image`는 하나의 I2I route다. 파라미터 설정은 긍정·부정 본문 위에 각각 `긍정 프롬프트 Prefix`, `부정 프롬프트 Prefix` textarea를 제공한다. prefix는 preset에서 본문과 independent field로 저장·복원하며 server는 prefix와 본문을 합성한 final prompt를 생성·Vault에 저장한다. 페이지 family tab으로 Anima와 Illustrious를 전환하며 local image 또는 owned stored image 한 장을 source로 사용한다. Krea2 tab은 local R2I에 필요한 `krea2_style_reference.safetensors` LoRA와 dedicated reference workflow가 아직 설치되지 않아 disabled 상태다. generic VAE I2I route로 대체하지 않는다. Krea2의 exact preset namespace와 Vault filter는 별도로 선택할 수 있다.

checkpoint와 LoRA selector는 ComfyUI relative model filename의 folder hierarchy를 button으로 표시한다. `전체`는 family scope 내 전체 model을, folder button은 해당 folder 및 하위 model만 표시한다. 하위 folder 선택 시 `전체` 바로 다음의 `바로 위 폴더` button으로 한 level씩 되돌아간다. family route가 바뀌면 selected folder filter를 root로 reset한다.

local source는 generation submit 때만 upload하고, stored source는 user-owned `file_id`를 보내 Storage의 원본 file을 재사용한다. I2I 소스 선택 modal은 `저장된 콘텐츠 → 생성 → T2I (Anima)`를 initial state로 열고, generated image picker는 `ANIMA`, `ILLUSTRIOUS`, `KREA2` family tab과 그 아래 `T2I`, `I2I` mode tab으로 정확한 metadata filter를 backend에 함께 전달한다. I2I preset은 `i2i_anima` 또는 `i2i_illustrious`만 사용하며 Denoise를 저장·적용할 수 있다. local/stored source preview의 선택 해제 action은 shared filled icon button을 사용한다.
