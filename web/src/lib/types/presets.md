# 이미지 모델·프리셋 타입

프리셋·이미지 생성에서 선택 가능한 family는 Anima·Illustrious·MOSS SFT·Qwen 2.1 Turbo다. MOSS는 T2I, Qwen은 I2I/R2I를 지원한다. FLUX 3는 선택 메뉴에서 제외한다. 기존 FLUX family·preset 타입은 과거 데이터 해석을 위해 유지한다. 이전 Krea2 family·preset 타입은 기존 Vault 상세 데이터 해석을 위해 남기며 신규 선택 tab에는 노출하지 않는다. 공통 family label과 API 기본 CFG·steps 타입을 제공한다.

`PresetValues`는 video steps·use_pdd·learned_3d upscale_mode·target_megapixels를 보존하며 VideoGenerationOptions의 pdd_available·learned_upscale_available로 해당 기능을 구분한다.

## MOSS SFT

이미지 family에 moss, 프리셋에 T2I 전용 t2i_moss를 추가한다. MOSS 레이아웃을 프리셋 값에 포함하며 저장된 이미지 선택·보관함·프리셋 목록은 공통 family 탭을 사용한다. MOSS에서는 I2I 모드 탭을 표시하지 않는다.

Qwen 2.1 Turbo는 qwen_image_2_1 family와 i2i_qwen_image_2_1 범주를 사용한다. 별도 T2I 범주는 제공하지 않는다.

Qwen 옵션의 prompt_enhancer_available로 로컬 I2I 강화 가중치·노드 준비 여부를 표시한다.

imageGenerationFamilyTabs는 프리셋·I2I용 현행 모델 목록이며 FLUX 3를 제외한다. 기존 imageModelFamilyTabs는 과거 Vault 필터를 위해 유지한다.
