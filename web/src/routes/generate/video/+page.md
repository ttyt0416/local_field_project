# MiniMax H3 동영상 생성 화면

I2V·FL2V·R2V를 tab으로 선택한다. 각 input은 device storage 또는 stored content selection modal에서 선택한다. existing file은 `file_id`로 전송해 owner check 뒤 재사용하고 local file은 generation submit 때만 multipart로 전송한다.

동영상 생성의 image source selector는 `저장된 콘텐츠 → 생성 → T2I (Anima)`를 initial state로 열고, `ANIMA`, `ILLUSTRIOUS`, `KREA2` family tab과 그 아래 `T2I`, `I2I` mode tab을 표시한다. selected category는 `/uploads`의 `generation_mode`와 `model_family` exact filter로 전송한다. video/audio reference는 image generation category filter 없이 기존 device selection을 유지한다.

I2V·FL2V·R2V source card는 원본 비율과 관계없이 12rem preview 높이를 사용해 original media dimensions와 해당 source 전용 `이 사이즈 사용` action을 card 바로 아래에 표시한다. action은 MiniMax H3의 1344 maximum과 32 multiple constraint에 맞춘 dimensions만 current video form에 적용한다.

스타일·전체 배경 input 하나와 duration에서 계산한 시간 구간별 action input을 분리한다. 예를 들어 30초 영상은 `0~10초`, `10~20초`, `20~30초` 구간을 각각 입력한다. duration 변경은 사라진 구간만 제거하고 남은 index의 input/improved value를 유지한다. `프롬프트 개선`은 browser가 공통 context와 현재 구간 action을 vLLM으로 하나씩 직렬 전송한다. 화면은 입력 프롬프트 1 → 개선 프롬프트 1 → 입력 프롬프트 2 → 개선 프롬프트 2 순서로 표시하며, 전체 style/background 수정은 all improved values를 reset하고 한 구간 action 수정은 그 구간 improved value만 reset한다. 각 block의 timeline clock은 global video time이 아니라 해당 segment의 `0초`부터 segment duration까지다. 예를 들어 11초 영상의 두 번째 block은 `0~1초`다. 10초 초과 sequence에서는 final frame 연결을 R2V 또는 I2V로 선택한다. R2V는 final frame을 Picture 1로 사용하고 selected image references는 Picture 2부터 유지하며 선택 image는 최대 8개다. I2V는 final frame을 next segment의 first frame으로 쓴다. 생성은 prompt 개선을 끈 경우 공통 context와 해당 구간 action을, 켠 경우 사용자가 submit한 segment별 proposal을 사용한다. result status에는 active `구간 n/N`과 sequence aggregate progress를 표시한다.
