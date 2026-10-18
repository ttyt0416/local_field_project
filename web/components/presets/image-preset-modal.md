# IMAGE 프리셋 모달

이미지 생성 preset을 저장·수정한다. type은 caller가 `t2i_anima`, `i2i_anima`, `t2i_illustrious`, `i2i_illustrious`, `t2i_krea2`, `i2i_krea2`, `i2i_flux3_klein` 중 하나로 전달하며, modal은 그 type을 그대로 create/update API에 보낸다. 수정 시에도 type을 전송하므로 다른 namespace의 preset을 수정할 수 없다. `긍정 프롬프트 Prefix`, `부정 프롬프트 Prefix`는 prompt 본문과 별도로 선택·저장·복원한다. checkpoint와 LoRA는 T2I와 같은 folder-filtered selection modal에서 선택하며, LoRA 선택 개수에는 제한이 없다.

T2I에는 prompt improvement를, I2I에는 Denoise를 각각 mode 전용 필드로 표시한다. Seed는 저장·수정 필수값이 아니다. 무작위를 선택하면 `random_seed=true`를 저장하고, 무작위가 아니면서 값이 비어 있으면 seed 관련 key를 저장하지 않는다. 공용 `Modal`의 `80dvh` 최대 높이와 내부 scroll을 사용한다.

width와 height는 기존 64~2048 product cap 없이 Comfy native 16~16384 range와 8 pixel step을 사용한다.

FLUX 3 Klein 편집은 `model_family="flux3_klein"`, `generation_mode="i2i"`, `i2i_flux3_klein` preset namespace로 구분한다. 신규 family 선택에서 Krea2는 제거하며 이전 생성 데이터는 유지한다.
FLUX 프리셋은 CFG·Denoise 1, API 기본 16 steps를 사용하고 크기를 32 배수로 선택한다.

## MOSS SFT

MOSS 프리셋은 T2I 레이아웃을 편집·보존한다. 출력 크기를 16 배수로 제한하며 DMD 설정을 적용할 수 있다. 참조 편집 설정은 제공하지 않는다.

Qwen 2.1 Turbo 프리셋은 출력 크기를 32배수로 맞추며 CFG 1·8스텝·전용 스케줄을 유지한다. Denoise는 편집용 1로 고정한다.

MOSS 레이아웃을 독립 저장 항목으로 선택해 편집·보존한다. Qwen의 LLM 강화 활성/비활성은 별도 프롬프트 개선 설정으로 저장하며, T2I용 개선된 프롬프트 textarea는 표시하지 않는다. Qwen 샘플러·스케줄 값은 공식 고정 설정으로 정규화한다.
