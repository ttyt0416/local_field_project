# 프리셋 관리

프리셋 관리는 `IMAGE`와 `VIDEO`를 별도 title로 표시한다. `IMAGE` 아래에는 3-column grid의 `T2I (Anima)`, `I2I (Anima)`, `T2I (Illustrious)`, `I2I (Illustrious)` 버튼을 둔다. 각 버튼은 정확히 하나의 preset type만 조회·생성·수정·삭제·기본 지정한다.

이미지 preset type은 `t2i_anima`, `i2i_anima`, `t2i_illustrious`, `i2i_illustrious`다. mode 또는 family 간 fallback·공유는 없다. 따라서 같은 이름의 preset이어도 type이 다르면 서로 영향을 주지 않으며, 사용자·exact type마다 기본 프리셋은 하나만 유지한다. `VIDEO`는 기존 `video` type을 유지한다.

이미지 modal은 T2I에서 prompt improvement를, I2I에서 Denoise를 해당 mode 전용 항목으로 표시한다. 선택한 값만 저장하며, load는 선택한 exact type의 저장 항목만 현재 설정에 덮어쓴다.
