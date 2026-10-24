# 리깅 좌표 검사

합성 GLB로 부모의 quaternion 회전·scale·translation 및 matrix 변환을 검증한다. 관절 사이에 일반 노드가 있을 때 부모 연결, 비활성 skin 제외, 일반 메시의 빈 리깅 결과, 잘린 GLB와 순환 계층 오류를 확인한다.

실행: `node --experimental-strip-types --test tests/rig-inspection.test.ts`
