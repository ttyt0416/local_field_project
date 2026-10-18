# 프리셋 관리

IMAGE·VIDEO tab과 이미지 family·mode tab을 제공한다. 신규 이미지 선택은 Anima·Illustrious·FLUX 3 Klein이며 FLUX는 `i2i_flux3_klein`으로 분리한다. family에 현재 mode가 없으면 해당 family의 I2I를 선택하고, FLUX에서 T2I를 선택하면 Anima T2I로 이동한다. Krea2 신규 선택은 제거했으며 이전 데이터를 삭제하지 않는다.

목록 조회·생성·수정·기본 지정·삭제는 정확한 preset type과 사용자 ownership을 유지한다. 이미지 옵션의 기본 CFG·steps를 preset editor에 전달한다. VIDEO namespace와 동작은 유지한다.

FLUX 3 Klein 편집은 `model_family="flux3_klein"`, `generation_mode="i2i"`, `i2i_flux3_klein` preset namespace로 구분한다. 신규 family 선택에서 Krea2는 제거하며 이전 생성 데이터는 유지한다.

MOSS 분류는 T2I 전용이며 선택 시 I2I 방식 탭을 표시하지 않는다.

Qwen 2.1 Turbo 분류는 I2I/R2I 전용이므로 T2I 방식 탭을 표시하지 않는다.

MOSS 레이아웃과 Qwen LLM 강화 저장 항목은 목록에서 사용자용 이름으로 표시한다.
