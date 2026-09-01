# Danbooru 태그 탐색기

`/tags`는 authenticated user가 local Postgres `danbooru_tags` DB를 탐색하는 메뉴다. `GET /tags`는 `search`, optional `category`, `page`를 받고 tag, category, post count, aliases와 total pagination을 반환한다. 결과는 tag exact match, alias exact match, tag prefix, alias prefix, then post count 순으로 정렬한다.

SearchBar는 300 ms debounce로 요청하고, category buttons는 현재 CSV에 존재하는 일반, 저작물, 캐릭터를 filter한다. 각 result card의 copy action은 tag text만 clipboard에 복사한다. prompt 자동 삽입, LLM, embedding service 요청은 하지 않는다.
