# MiniMax Music 3 음악 생성

`/generate/music`는 MiniMax Music 3 local generation UI와 contract를 먼저 제공한다. 로그인 뒤 `GET /generation/music/options`를 호출해 model name과 service availability를 읽는다. 현재 local service, model download, inference worker가 없으므로 `service_available=false`이며 form은 음악 설명과 tagged lyrics를 편집할 수 있지만 생성 button은 deactive다.

음악 설명은 genre, mood, vocal, instrumentation, arrangement를 입력하고 가사는 `[Verse]`, `[Chorus]`, `[Bridge]`, `[Instrumental]` 같은 line-based section tag를 허용한다. service 연결 뒤에만 durable job submit, status, audio player, Storage output, Vault MUSIC을 추가한다.
