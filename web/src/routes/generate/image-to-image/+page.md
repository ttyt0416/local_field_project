# I2I

`/generate/image-to-image?family=`는 Anima·Illustrious·FLUX 3 Klein을 선택한다. Krea2 선택은 제거했다. local image 또는 소유권이 확인된 저장 이미지 한 장을 기본 source로 사용하며 submit 전에는 업로드하지 않는다. 기존 folder selector와 생성 worker·SSE·취소·Vault 연결을 재사용한다.

FLUX는 `i2i_flux3_klein` 프리셋을 사용한다. source를 참조해 수정 지시를 수행하며 공식 프롬프트 확장 모델을 항상 거친다. 기본 설정은 CFG 1, 16 steps, Euler·Simple이며 CFG는 고정하고 negative prompt·Denoise 입력은 표시하지 않는다. 크기는 32~16384의 32 배수이며 source 크기 적용도 같은 간격으로 반올림한다. Anima·Illustrious는 기존 Denoise와 8 pixel multiple을 유지한다.

저장된 콘텐츠 선택기는 Anima T2I에서 시작한다. FLUX family 선택 시 I2I category로 전환하며, 해당 family에 T2I가 없을 때 T2I 선택은 Anima T2I로 이동한다. 옵션 기본 CFG·steps는 family별 API 응답을 사용하고 저장된 프리셋·재생성 설정은 그 위에 적용한다. Qwen Image 2.1은 취소되어 표시하지 않는다.

FLUX는 원본 외 추가 참조를 최대 9장 선택한다. 기기 파일은 여러 장 선택할 수 있고 저장된 이미지도 함께 추가할 수 있다. preview·삭제·앞뒤 순서 이동을 제공한다. 프롬프트의 <ref_image_0>은 원본이며 추가 참조는 1부터 시작한다. 실제 submit 시에만 새 파일을 업로드하며 재생성 시 저장된 참조와 순서를 복원한다.

현재 FLUX 가중치·인코더·프롬프트 확장 모델·VAE는 사용자 요청으로 제거했다. 다중 참조 UI와 연결 코드는 유지하며, 모델 미설치 상태에서는 생성 옵션 API가 설치 필요 오류를 반환한다.

## MOSS SFT

MOSS는 T2I 전용이므로 I2I 모델 탭·설정·요청에서 제외한다. 기존 family=moss I2I 주소는 MOSS T2I 페이지로 이동한다. 소스 선택창에서 MOSS 생성물을 찾을 때도 T2I만 표시한다. 다른 편집 모델의 다중 참조 UI는 유지한다.

Qwen 2.1 Turbo 탭은 한 장 수정(I2I)과 원본 포함 최대 10장 참조 생성(R2I)을 제공한다. 추가 참조가 있으면 페이지 제목이 R2I로 바뀐다. 참조 추가·정렬·삭제와 기기/저장소 선택을 재사용하고 원본 <image1>, 추가 참조 <image2>~<image10> 순서를 안내한다. 공식 8스텝·CFG 1·Euler·전용 스케줄을 고정하고 Denoise·negative prompt를 노출하지 않는다. 프리셋과 보관함 재생성에 동일한 family·참조를 전달한다.

Qwen LLM 프롬프트 강화는 기본 켜짐이며 체크박스로 끌 수 있다. 선택한 원본·참조와 함께 생성 그래프에서 실행한다. 프리셋 초기값·저장·수정·불러오기 및 보관함 재생성에서 활성 상태를 유지한다.
