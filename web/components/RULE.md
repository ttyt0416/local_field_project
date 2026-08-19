# 컴포넌트 규칙

버튼은 기본적으로 다음 3가지 상태를 제공해야 합니다.

- `active`
- `deactive`
- `loading`

토스트는 다음 3가지 상태를 제공해야 합니다.

- `positive`
- `negative`
- `info`

## 비동기 버튼

버튼이 비동기 처리를 시작하면 `loading` 상태로 표시하고 비활성화해야 합니다.
