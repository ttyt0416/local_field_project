# T2I 생성 컴포넌트

모델 family는 라우트가 prop으로 전달한다. 모델 탭은 onselect 콜백으로 상위 상태만 바꾸며 페이지 이동이나 전체 새로고침을 하지 않는다. 상위 keyed 블록에서 family마다 컴포넌트를 교체해 폼·프리셋·모달 상태를 분리한다.

설치된 Illustrious 체크포인트가 없으면 안내를 표시하고 생성은 비활성화하되 프리셋 사용은 유지한다. 긴 체크포인트명은 그리드 자식과 버튼의 최소 너비를 제한하고 한 줄 말줄임 및 title로 표시한다. 선택 모달의 모델명은 줄바꿈한다.

# T2I 결과 표시

`/generate/image`는 하나의 T2I route다. negative prompt는 빈 값으로 시작한다. 파라미터 설정은 긍정·부정 본문 위에 각각 `긍정 프롬프트 Prefix`, `부정 프롬프트 Prefix` textarea를 제공한다. prefix는 preset과 generation record에서 본문과 independent field로 저장·복원하며, server는 ComfyUI conditioning에서만 prefix와 본문을 합성한다. LoRA 선택 개수에는 제한이 없다. 페이지 family tab으로 Anima·Illustrious·MOSS SFT를 전환하며 query family에 맞는 model·LoRA options를 사용한다. Krea2 신규 생성과 선택은 제거했다. Anima는 Diffusion Model, Illustrious는 full checkpoint를 사용한다.

checkpoint와 LoRA selector는 ComfyUI relative model filename의 folder hierarchy를 button으로 표시한다. `전체`는 family scope 내 전체 model을, folder button은 해당 folder 및 하위 model만 표시한다. 하위 folder 선택 시 `전체` 바로 다음의 `바로 위 폴더` button으로 한 level씩 되돌아간다. 선택 값은 backend가 family-scoped option 목록 안에 있는지 다시 검증한다.

프리셋은 Anima `t2i_anima`, Illustrious `t2i_illustrious` namespace를 사용한다. 서로 다른 family/mode preset은 불러오거나 저장하지 않는다. `프롬프트 개선`은 Anima에서는 기존 Danbooru tags와 자연어 개선을 유지하고, Illustrious에서는 검증된 comma-separated Danbooru tags만 반환한다.

width와 height는 기존 64~2048 product cap 없이 Comfy native 16~16384 range의 8 pixel multiple을 사용한다.

## MOSS SFT

MOSS SFT 탭은 공통 MossControls로 사물·인물·텍스트 레이아웃을 편집한다. 박스는 드래그·크기 조절·수치 편집할 수 있다. MOSS 설정을 요청·프리셋·재생성에 전달하며 출력 크기는 16 배수다. 프롬프트 개선은 사용하지 않고 장면 설명을 직접 전달한다. MOSS 컨트롤은 레이아웃 버튼과 영역 편집만 제공하며 별도 설정 제목과 DMD 적용 버튼은 표시하지 않는다.

MOSS 레이아웃을 별도 프리셋 저장 항목으로 제공한다. 선택 해제 시 레이아웃을 덮어쓰지 않으며 레이아웃만 선택해 저장할 수 있다. MOSS에는 프롬프트 개선 저장 항목을 표시하지 않는다.

긍정·부정 프롬프트 아래 PromptLibrary를 제공한다. 이미지용 저장 문장을 불러오면 해당 입력의 뒤에 추가하며 모델·프리셋 설정은 건드리지 않는다.

긍정 입력에 저장 문장을 추가하면 이전 개선 프롬프트를 비워 변경된 원문에 맞춰 다시 개선하도록 한다.
