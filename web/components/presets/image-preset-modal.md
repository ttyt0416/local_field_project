# IMAGE 프리셋 모달

이미지 생성 preset을 저장·수정한다. type은 caller가 반드시 `t2i_anima`, `i2i_anima`, `t2i_illustrious`, `i2i_illustrious` 중 하나로 전달하며, modal은 그 type을 그대로 create/update API에 보낸다. 수정 시에도 type을 전송하므로 다른 namespace의 preset을 수정할 수 없다.

T2I에는 prompt improvement를, I2I에는 Denoise를 각각 mode 전용 필드로 표시한다. 공용 `Modal`의 `80dvh` 최대 높이와 내부 scroll을 사용한다.
