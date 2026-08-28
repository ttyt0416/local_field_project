# 프리셋 요청 테스트

`PresetCreateRequest`와 `PresetUpdateRequest`가 이름을 정리하고 선택된 값만 보존하는지, 기본 프리셋 여부를 수용하는지, 정의되지 않은 값과 `t2i` 외 타입을 거부하는지 확인한다. 사용자·타입별 기본 프리셋 중복 방지는 PostgreSQL partial unique index가 담당한다.
