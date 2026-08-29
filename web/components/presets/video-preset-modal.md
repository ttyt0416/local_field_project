# VIDEO GEN 프리셋 모달

영상 생성 프리셋의 저장·수정 모달이다. prompt, mode, 크기, 길이, seed 중 선택한 필드만 `video` 타입으로 저장한다. 크기는 API에서 `width`·`height`, seed 무작위 여부는 `random_seed`로 보존하며, 수정 시 이 값을 `VIDEO GEN` 필드 선택 상태로 복원한다. 공용 `Modal`의 `80dvh` 최대 높이와 내부 스크롤을 사용한다.
