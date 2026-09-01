# T2I 결과 표시

`/generate/image`는 하나의 T2I route다. 페이지 family tab으로 Anima와 Illustrious를 전환하며, 각각 query family에 맞는 checkpoint·LoRA options와 backend loader를 사용한다. Anima는 Diffusion Model, Illustrious는 full checkpoint다. Krea2 tab은 generator workflow와 generation request family validation이 제공될 때까지 disabled option으로만 표시한다. Krea2의 exact preset namespace와 Vault filter는 별도로 선택할 수 있다.

checkpoint와 LoRA selector는 ComfyUI relative model filename의 folder hierarchy를 button으로 표시한다. `전체`는 family scope 내 전체 model을, folder button은 해당 folder 및 하위 model만 표시한다. 하위 folder 선택 시 `전체` 바로 다음의 `바로 위 폴더` button으로 한 level씩 되돌아간다. 선택 값은 backend가 family-scoped option 목록 안에 있는지 다시 검증한다.

프리셋은 Anima `t2i_anima`, Illustrious `t2i_illustrious` namespace를 사용한다. 서로 다른 family/mode preset은 불러오거나 저장하지 않는다.
