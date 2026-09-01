# MiniMax H3 동영상 생성 화면

I2V·FL2V·R2V를 tab으로 선택한다. 각 input은 device storage 또는 stored content selection modal에서 선택한다. existing file은 `file_id`로 전송해 owner check 뒤 재사용하고 local file은 generation submit 때만 multipart로 전송한다.

동영상 생성의 image source selector는 `저장된 콘텐츠 → 생성 → T2I (Anima)`를 initial state로 열고, `ANIMA`, `ILLUSTRIOUS`, `KREA2` family tab과 그 아래 `T2I`, `I2I` mode tab을 표시한다. selected category는 `/uploads`의 `generation_mode`와 `model_family` exact filter로 전송한다. video/audio reference는 image generation category filter 없이 기존 device selection을 유지한다.

R2V source card마다 original media dimensions와 해당 source 전용 `이 사이즈 사용` action을 표시한다. action은 MiniMax H3의 1344 maximum과 32 multiple constraint에 맞춘 dimensions만 current video form에 적용한다.

길이가 10초를 넘으면 duration에서 계산한 개수만큼 `10초 구간 프롬프트` textarea를 표시한다. 각 block의 timeline clock은 global video time이 아니라 해당 segment의 `0초`부터 segment duration까지다. 예를 들어 11초 영상의 두 번째 block은 `0–1초`다. 첫 구간은 selected mode로 생성하고 후속 구간은 서버가 직전 output의 실제 마지막 frame을 `<Picture 1>`로 넣은 R2V로 생성한다. `전체 구간 개선`은 vLLM에 구간별 duration과 prior scene context를 순서대로 보내며, returned proposal은 원문과 분리된 editable textarea에 표시한다. 생성은 각 구간 원문 또는 사용자가 검토·수정한 proposal을 명시적으로 submit할 때만 시작한다. result status에는 active `구간 n/N`과 sequence aggregate progress를 표시한다.
