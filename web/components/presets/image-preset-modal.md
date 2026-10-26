# IMAGE 프리셋 모달

이미지 생성 preset을 저장·수정한다. type은 caller가 `t2i_anima`, `i2i_anima`, `t2i_illustrious`, `i2i_illustrious`, `t2i_krea2`, `i2i_krea2` 중 하나로 전달하며, modal은 그 type을 그대로 create/update API에 보낸다. 수정 시에도 type을 전송하므로 다른 namespace의 preset을 수정할 수 없다. `긍정 프롬프트 Prefix`, `부정 프롬프트 Prefix`는 prompt 본문과 별도로 선택·저장·복원한다. checkpoint와 LoRA는 T2I와 같은 folder-filtered selection modal에서 선택하며, LoRA 선택 개수에는 제한이 없다.

T2I·I2I 모두 프롬프트 개선 사용 여부와 개선된 본문을 저장·편집한다. 일반 I2I에는 Denoise를 표시한다. Seed는 저장·수정 필수값이 아니다. 무작위를 선택하면 `random_seed=true`를 저장하고, 무작위가 아니면서 값이 비어 있으면 seed 관련 key를 저장하지 않는다. 공용 `Modal`의 `80dvh` 최대 높이와 내부 scroll을 사용한다.

width와 height는 기존 64~2048 product cap 없이 Comfy native 16~16384 range와 8 pixel step을 사용한다.


## MOSS


Qwen 2.1 Turbo 프리셋은 출력 크기를 32배수로 맞추며 CFG 1·8스텝·전용 스케줄을 유지한다. Denoise는 편집용 1로 고정한다.

MOSS 레이아웃을 독립 저장 항목으로 선택해 편집·보존한다. Qwen도 프롬프트 개선 활성 상태와 자연어 개선 결과를 같은 저장 항목과 textarea로 편집한다. Qwen 샘플러·스케줄 값은 공식 고정 설정으로 정규화한다.

MOSS 편집은 레이아웃 버튼과 영역 편집만 제공한다. 별도 MOSS 설정 제목과 DMD 바로가기 버튼은 제거했다. 긴 체크포인트명은 버튼 안에서 말줄임한다.
