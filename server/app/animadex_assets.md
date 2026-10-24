# AnimaDex 로컬 썸네일

공식 export manifest의 `r2_base`, `prefixes`, `index_url`을 사용한다. 원격 파일명은 공식 sanitize_filename 규칙으로 트리거(캐릭터·아티스트) 또는 시리즈 slug에서 만들고, 로컬 파일명은 kind와 slug의 SHA-256으로 고정해 경로 탈출·파일명 길이·종류 간 충돌을 방지한다.

`ANIMADEX_DATA_DIR` 아래에 `{characters|artists|series}/{hash}.webp`와 `thumbnails.json`을 저장한다. 기본 경로는 프로젝트 `.runtime/tag-catalogues/animadex`이며 production에서는 동일한 호스트 디렉터리를 명시적인 컨테이너 경로로 bind mount한다. 이미지 데이터는 Git이나 Docker build context에 들어가지 않는다.

최초 가져오기는 공식 full 요청을 사용하고 48시간 제한(429)이면 delta manifest로 전환한다. 이후에는 저장한 항목별 버전·URL과 로컬 파일 유무를 비교해 변경·누락 항목만 받는다. 기본 8개 작업으로 내려받으며 CLI --concurrency로 1~32개를 지정할 수 있다. 각 작업은 검증된 HTTPS 연결을 재사용하고 끊긴 연결만 한 번 재연결한다. WebP magic 및 RIFF 길이를 검증한 뒤 임시 파일을 원자적으로 교체한다. 250개마다 상태를 저장해 중단 후 재시도를 지원한다. 실패한 파일은 이전 이미지·버전을 보존하며 다음 가져오기에서 다시 시도한다. 제공처 404는 별도 missing 개수로 집계하고 다른 오류와 구분한다. 동시 가져오기는 파일 잠금으로 막는다.

로그인한 사용자의 검색 요청에서는 파일 유무·mtime을 읽고 로컬 썸네일 API의 이미지 전용 서명 URL을 반환한다. 서버 인증 키와 용도를 구분한 HMAC 메시지로 종류·파일 키·만료 시간을 묶으며 15분 동안 해당 이미지 한 개만 읽을 수 있다. 다른 파일·종류·만료 시간으로 바꾸면 서명이 맞지 않는다. export 토큰이나 로그인 Bearer는 이미지 URL에 들어가지 않는다.

썸네일이 없는 항목은 `thumb_url: null`이다. API나 브라우저가 외부 CDN으로 대체 요청하지 않는다. 원본 PNG 일괄 다운로드는 이 썸네일 가져오기의 범위에 포함하지 않는다.

[공식 가져오기 스크립트](https://github.com/zetaneko/AnimaDex/blob/main/scripts/import_from_site.py), [공식 파일명 규칙](https://github.com/zetaneko/AnimaDex/blob/main/animadex/db.py)을 기준으로 구현했다.

카탈로그 manifest와 index의 데이터셋 버전이 일치하는지도 파일·DB 교체 전에 검증한다.

실제 버전 1780120177에서 캐릭터 36,490개·아티스트 15,877개·시리즈 3,698개, 총 56,065개 WebP를 저장했다. 제공처 404는 8개이고 나머지 실패는 없다. 동일 버전 재실행은 저장된 이미지 56,065개를 건너뛰고 mtime을 변경하지 않았다.
