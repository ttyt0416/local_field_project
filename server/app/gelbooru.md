# Gelbooru 로컬 태그

`GET /tags/gelbooru`는 인증 후 PostgreSQL gelbooru_tags만 조회한다. 외부 API·임베딩 서비스를 호출하지 않는다. 검색은 공백을 underscore로 정규화하고 LIKE 와일드카드를 escape하며 일치순·사용순·분류·페이지를 지원한다. 별칭이 없는 원본이므로 aliases는 빈 목록이다.

`python -B -m app.gelbooru /tag-data/gelbooru_tags_2026-06-11.jsonl`로 전체 JSONL을 가져온다. COPY 스테이징·중복 제거·테이블 교체·import 시각 갱신은 한 트랜잭션이므로 실패 시 기존 데이터가 보존된다. 같은 원본을 반복 가져올 수 있다.

원본은 [DraconicDragon/Gelbooru-Tags-Full_2026-06-11](https://huggingface.co/datasets/DraconicDragon/Gelbooru-Tags-Full_2026-06-11)의 2026-06-11 전체 스냅샷이다. 145081565바이트 JSONL의 SHA-256은 ba99cbd800f9e3a0779a24026a9951b90c2918ef9f334b9c97697499effa3c41. 빈 이름 5행을 제외하고 같은 이름은 사용 수가 가장 큰 행으로 합쳐 1393566개를 유지한다. 운영 원본은 `.runtime/tag-catalogues/`에 두며 Git·서버 Docker build context에 포함하지 않는다. 라이선스는 데이터셋의 Apache-2.0 표기를 따른다.
