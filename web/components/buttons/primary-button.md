# PrimaryButton

`PrimaryButton`은 기본 primary 동작과 파괴적 동작을 공용으로 지원한다. 삭제·탈퇴처럼 되돌릴 수 없는 작업은 `variant="destructive"`를 사용해 destructive 색상 토큰과 흰색 전경색을 적용한다.

선택적인 form 속성을 실제 button에 전달한다. 폼 밖의 생성 버튼도 해당 폼을 제출해 기본 입력 검증과 기존 onsubmit 처리를 함께 사용한다.
