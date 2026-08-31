# 모델 folder filter

ComfyUI가 반환하는 model relative filename에서 모든 ancestor folder를 계산한다. 빈 filter는 전체 model을 보여주고, 선택한 folder는 해당 folder와 그 하위의 model만 표시한다. 선택 folder가 root가 아니면 immediate parent filter를 반환해 `바로 위 폴더` button이 한 level씩 돌아갈 수 있게 한다.
