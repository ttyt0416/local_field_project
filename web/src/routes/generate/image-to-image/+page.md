# I2I

`/generate/image-to-image?family=anima|illustrious`는 local image 또는 owned stored image 한 장을 source로 사용한다. Anima와 Illustrious는 해당 family options만 로드하며 route title은 `I2I (Anima)` 또는 `I2I (Illustrious)`로 표시한다.

checkpoint와 LoRA selector는 ComfyUI relative model filename의 folder hierarchy를 button으로 표시한다. `전체`는 family scope 내 전체 model을, folder button은 해당 folder 및 하위 model만 표시한다. 하위 folder 선택 시 `전체` 바로 다음의 `바로 위 폴더` button으로 한 level씩 되돌아간다. family route가 바뀌면 selected folder filter를 root로 reset한다.

local source는 generation submit 때만 upload하고, stored source는 user-owned `file_id`를 보내 Storage의 원본 file을 재사용한다. generated image picker는 T2I/I2I × Anima/Illustrious metadata filter를 backend에 함께 전달한다. I2I preset은 `i2i_anima` 또는 `i2i_illustrious`만 사용하며 Denoise를 저장·적용할 수 있다.
