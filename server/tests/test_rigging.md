# 리깅 통합 계약 검증

소유권 확인, 잘못된 GLB 차단, terminal 결과의 DB 조회, 중복 완료 저장 방지, 취소 실패 시 DB 보존, SSE 오류 메시지, 공유 MESH 보존과 업로드 원본 정리를 검증한다. 모델 계산은 별도 GPU smoke test로 확인한다.
완료된 리깅 결과의 상태 조회는 worker 없이 DB에서 인증된 `vault/3d/{generation_id}/model` URL을 제공한다.

## 동작·오류 기록

원격 실패 기록 검증 대상을 record_remote_error로 변경했다.
