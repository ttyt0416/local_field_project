# 이미지 프롬프트 개선 유틸

T2I·I2I가 동일한 POST generation/image/enhance-prompt 경로를 사용하도록 model family·원문을 전달하고 편집 가능한 개선 본문을 반환한다. apiJson의 인증·원문 오류 기록·API 레이턴시 기록을 재사용하며 600초 timeout을 유지한다. 비어 있는 결과는 오류로 처리하고 caller의 try/catch에서 toast를 표시한다. Anima·MOSS는 태그와 자연어를 사용한다.


이미지 모델 선택과 생성·프리셋·저장소 경로는 현재 지원하는 Anima·MOSS 범주만 사용한다.

minimax_h3_image도 공통 이미지 프롬프트 개선 API와 오류 처리·텔레메트리를 사용한다.
