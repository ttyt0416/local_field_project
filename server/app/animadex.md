# AnimaDex 로컬 카탈로그

`/tags/catalogue/{characters|artists|series}`는 인증 후 PostgreSQL만 조회한다. 검색·정렬·페이지·시리즈 필터에서 외부 검색 API나 임베딩 모델을 호출하지 않는다. 로컬 데이터가 없으면 503과 마지막 import 오류를 반환하며 외부 검색으로 대체하지 않는다.

`python -B -m app.animadex`는 서버 ANIMADEX_EXPORT_TOKEN으로 공식 `/api/export/manifest`에 인증하고 두 CSV를 가져온다. 토큰은 정확한 HTTPS animadex.net manifest 요청에만 헤더로 보내며 blobs.animadex.net CSV 요청에는 보내지 않는다. 자동 리디렉션·임의 호스트·원문 로그를 허용하지 않는다. `.env.production` 값은 Git·응답·브라우저에 포함하지 않는다.

가져오기는 캐릭터·아티스트·캐릭터를 묶은 시리즈 메타데이터를 원자적으로 교체한다. 빈 파일·잘못된 필드·실패한 다운로드는 기존 데이터를 유지하고 마지막 오류를 기록한다. 썸네일은 이 메타데이터 import에 포함하지 않으며 검색 시 외부 이미지를 불러오지 않는다. 수동 CSV는 `--csv-dir DIR --version VERSION`으로 읽을 수 있다.

이번 실제 연결에서는 export 인증은 HTTP 200, 공식 CSV CDN은 SSL WRONG_VERSION_NUMBER 오류다. 초기 카탈로그를 받지 못해 세 탭에서 준비 실패를 표시한다. [공식 export 절차](https://github.com/zetaneko/AnimaDex/blob/main/docs/import-from-site.md), [CSV 필드](https://github.com/zetaneko/AnimaDex/blob/main/docs/data-format.md)를 기준으로 구현했다.
