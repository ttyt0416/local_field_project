# Danbooru 태그 탐색기

`/tags`는 authenticated user가 local Postgres `danbooru_tags` DB를 탐색하는 메뉴다. `GET /tags`는 `search`, optional `category`, `sort`, `page`를 받고 tag, category, post count, aliases와 total pagination을 반환한다. `match`는 tag exact, alias exact, tag prefix, alias prefix, then post count 순이다. `similarity`는 검색어 embedding과 stored tag embedding의 pgvector cosine distance 순이고, `usage`는 text/alias match 결과를 post count 순으로 정렬한다. empty search의 `similarity`는 embedding request를 하지 않고 usage order로 fallback한다.

SearchBar는 300 ms debounce로 요청하고, category buttons는 현재 CSV에 존재하는 일반, 저작물, 캐릭터를 filter한다. 각 result card의 copy action은 tag text만 clipboard에 복사한다. `match`와 `usage`는 LLM이나 embedding service 요청을 하지 않고, `similarity`만 pgvector query vector를 위한 one embedding request를 한다.
