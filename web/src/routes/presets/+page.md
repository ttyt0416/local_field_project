# 프리셋 관리

프리셋 관리는 visible `IMAGE`/`VIDEO` title 없이 최상단 `IMAGE`, `VIDEO` 2-tab을 표시한다. IMAGE가 선택되면 그 아래 `ANIMA`, `ILLUSTRIOUS`, `KREA2` family 3-tab과 `T2I`, `I2I` mode 2-tab을 동일한 간격으로 표시한다. 기본 선택은 `IMAGE` → `ANIMA` → `T2I`다. 새 프리셋 button은 이 tab cluster 바로 아래 우측에 둔다. 각 조합은 정확히 하나의 preset type만 조회·기본 지정·삭제한다. Krea2 T2I는 installed Turbo workflow options를 사용해 새 preset 생성·수정을 제공한다. Krea2 I2I는 dedicated style-reference LoRA workflow가 없으므로 disabled 상태다.

이미지 preset type은 `t2i_anima`, `i2i_anima`, `t2i_illustrious`, `i2i_illustrious`, `t2i_krea2`, `i2i_krea2`다. mode 또는 family 간 fallback·공유는 없다. 따라서 같은 이름의 preset이어도 type이 다르면 서로 영향을 주지 않으며, 사용자·exact type마다 기본 프리셋은 하나만 유지한다. `VIDEO`는 기존 `video` type을 유지한다.

이미지 modal은 T2I에서 prompt improvement를, I2I에서 Denoise를 해당 mode 전용 항목으로 표시한다. 선택한 값만 저장하며, load는 선택한 exact type의 저장 항목만 현재 설정에 덮어쓴다.
