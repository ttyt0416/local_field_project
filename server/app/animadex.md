# AnimaDex 로컬 카탈로그

`/tags/catalogue/{characters|artists|series}`는 인증 후 PostgreSQL만 조회한다. 검색·정렬·페이지·시리즈 필터에서 외부 검색 API나 임베딩 모델을 호출하지 않는다. 로컬 데이터가 없으면 503과 마지막 import 오류를 반환하며 외부 검색으로 대체하지 않는다.

`python -B -m app.animadex`는 서버 ANIMADEX_EXPORT_TOKEN으로 공식 `/api/export/manifest`에 인증하고 두 CSV를 가져온다. 토큰은 정확한 HTTPS animadex.net manifest 요청에만 헤더로 보내며 blobs.animadex.net CSV 요청에는 보내지 않는다. 자동 리디렉션·임의 호스트·원문 로그를 허용하지 않는다. `.env.production` 값은 Git·응답·브라우저에 포함하지 않는다.

가져오기는 캐릭터·아티스트·캐릭터를 묶은 시리즈 메타데이터를 원자적으로 교체하고 공식 WebP 썸네일을 로컬에 저장한다. CSV·썸네일 인덱스·경로 검증을 통과한 뒤 메타데이터를 반영한다. 빈 파일·잘못된 필드·실패한 메타데이터 다운로드는 기존 데이터를 유지하고 마지막 오류를 기록한다. 개별 썸네일 실패는 기존 이미지를 보존하고 재시도 가능한 상태로 남기며 warning에 실패 개수를 표시한다. 수동 `--csv-dir DIR --version VERSION`은 기존처럼 메타데이터만 가져온다.

`GET /tags/catalogue/{kind}/thumbnail/{key}`는 유효한 이미지 전용 서명 URL 또는 기존 로그인 Bearer 인증으로 로컬 파일만 `image/webp`로 반환한다. 서명 없는 익명 요청은 401, 만료·변조된 서명은 403이다. key는 소문자 64자리 hex만 허용한다. 인증된 검색 응답은 저장된 파일에 한해 상대 thumb_url, mtime 버전, 15분 만료·서명을 포함하며 브라우저로 export 토큰·CDN 주소를 전달하지 않는다. private cache와 nosniff를 설정한다. 썸네일 저장·delta 상태는 `animadex_assets.md`에 정리했다.

이전 SSL WRONG_VERSION_NUMBER는 로컬 ASUS 공유기의 AiProtection 차단 페이지가 TLS 대신 HTTP로 반환되어 발생했다. 차단 해제 후 버전 1780120177의 메타데이터를 정상 가져왔다. [공식 export 절차](https://github.com/zetaneko/AnimaDex/blob/main/docs/import-from-site.md), [CSV 필드](https://github.com/zetaneko/AnimaDex/blob/main/docs/data-format.md)를 기준으로 구현했다.

## 동작·오류 기록

썸네일 재시도, HTTP·네트워크 실패, 가져오기 오류를 record_exception으로 보존한다. HTTP 본문은 기록 스레드가 읽고 닫으며 가져오기 실패 상태도 원인 문구를 저장한다.
