# MiniMax Music 3 contract

`GET /generation/music/options`는 로그인한 사용자에게 현재 Music 3 model name과 local service availability를 반환한다. 현재는 service를 시작하거나 model을 내려받지 않으므로 `service_available`은 `false`다.

`music_generations`는 이후 durable Music 3 job lifecycle을 위한 table이다. owner, prompt/client ID, status, music description, lyrics, optional seed, output Storage metadata, actual duration, size, timestamps, favorite, view count를 보관한다. 현재 options API와 UI는 이 table에 row를 만들지 않는다. local Music 3 service가 준비된 뒤에만 create job endpoint, worker, Storage upload, Vault MUSIC을 추가한다.
