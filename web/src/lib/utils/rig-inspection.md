# GLB 리깅 검사

GLB의 JSON chunk만 읽어 활성 scene의 skin 참조, JOINTS_0·WEIGHTS_0를 가진 스킨 메시, 애니메이션 수를 확인한다. 관절 노드의 local matrix 또는 translation·quaternion rotation·scale과 부모 변환을 합성해 모델 좌표의 관절 위치 및 부모 연결을 반환한다. 선언만 있고 활성 scene에서 사용하지 않는 메시·skin은 제외한다. 잘못된 헤더·범위·순환 계층은 오류로 처리한다.

결과는 파일의 기본 자세를 나타낸다. 가중치 품질 평가나 애니메이션 생성·편집은 하지 않는다.
