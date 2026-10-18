# Database tests

Video generation insert coverage verifies persisted `steps` and `use_pdd` parameter order with the existing metadata contract.

참조 JSONB의 저장과 SQL 인자 수, crop row의 참조 복사, 참조 중인 Storage 파일 보존을 검증한다.

## MOSS SFT

MOSS 설정 JSON의 insert 매개변수와 참조 이미지 매개변수가 별도로 직렬화되는지 확인한다. 실제 PostgreSQL 임시 테이블에서 insert/read와 편집본 복사도 확인했고 트랜잭션은 롤백했다.

이미지 INSERT의 SQL placeholder 수와 reference_images·MOSS layout·LLM 활성 플래그 보존을 확인한다.
