import unittest
from unittest.mock import MagicMock, patch

from app.danbooru import _TAG_PAGE_SIZE, _like_escape, list_danbooru_tags
from app.configs.constants import settings


class DanbooruTagBrowseTest(unittest.TestCase):
    def _connection(self, *, total: int, rows: list[tuple[object, ...]]) -> MagicMock:
        connection = MagicMock()
        connection.__enter__.return_value = connection
        count_result = MagicMock()
        count_result.fetchone.return_value = (total,)
        tags_result = MagicMock()
        tags_result.fetchall.return_value = rows
        connection.execute.side_effect = [count_result, tags_result]
        return connection

    def test_search_uses_literal_tag_and_alias_matches_before_count(self) -> None:
        connection = self._connection(
            total=2,
            rows=[
                ("blue_hair", 0, 120, ["azure_hair"]),
                ("hair", 0, 80, []),
            ],
        )
        with patch("app.danbooru.get_connection", return_value=connection):
            items, total = list_danbooru_tags(search="Blue Hair", category=0, page=2)

        self.assertEqual(total, 2)
        self.assertEqual(items[0], {"tag": "blue_hair", "category": 0, "post_count": 120, "aliases": ["azure_hair"]})
        count_query, count_params = connection.execute.call_args_list[0].args
        select_query, select_params = connection.execute.call_args_list[1].args
        self.assertIn("category = %s", count_query)
        self.assertEqual(count_params, [r"%blue\_hair%", r"%blue\_hair%", 0])
        self.assertIn("WHEN normalized_tag = %s THEN 0", select_query)
        self.assertEqual(select_params[-2:], [_TAG_PAGE_SIZE, _TAG_PAGE_SIZE])

    def test_empty_search_returns_popular_tags_from_first_page(self) -> None:
        connection = self._connection(total=1, rows=[("1girl", 0, 1000, [])])
        with patch("app.danbooru.get_connection", return_value=connection):
            items, total = list_danbooru_tags()

        self.assertEqual(items, [{"tag": "1girl", "category": 0, "post_count": 1000, "aliases": []}])
        self.assertEqual(total, 1)
        query, params = connection.execute.call_args_list[1].args
        self.assertIn("ORDER BY post_count DESC, tag ASC", query)
        self.assertEqual(params, [_TAG_PAGE_SIZE, 0])

    def test_similarity_sort_uses_pgvector_without_text_match_filter(self) -> None:
        connection = self._connection(total=1, rows=[("blue_hair", 0, 1000, [])])
        with (
            patch("app.danbooru.get_connection", return_value=connection),
            patch("app.danbooru._request_embeddings", return_value=[[0.25] * settings.embedding_dimensions]) as request,
        ):
            items, total = list_danbooru_tags(search="blue hair", sort="similarity")

        self.assertEqual(items[0]["tag"], "blue_hair")
        self.assertEqual(total, 1)
        request.assert_called_once_with(["blue hair"])
        count_query, count_params = connection.execute.call_args_list[0].args
        select_query, select_params = connection.execute.call_args_list[1].args
        self.assertIn("embedding IS NOT NULL", count_query)
        self.assertNotIn("normalized_tag LIKE", count_query)
        self.assertEqual(count_params, [])
        self.assertIn("ORDER BY embedding <=> %s::vector", select_query)
        self.assertEqual(select_params[-2:], [_TAG_PAGE_SIZE, 0])

    def test_usage_sort_keeps_text_match_filter_but_orders_by_post_count(self) -> None:
        connection = self._connection(total=1, rows=[("blue_hair", 0, 1000, [])])
        with patch("app.danbooru.get_connection", return_value=connection):
            list_danbooru_tags(search="blue", sort="usage")

        query, _ = connection.execute.call_args_list[1].args
        self.assertIn("normalized_tag LIKE", query)
        self.assertIn("ORDER BY post_count DESC, tag ASC", query)

    def test_like_escape_treats_tag_characters_as_literals(self) -> None:
        self.assertEqual(_like_escape(r"foo_bar%\\baz"), r"foo\_bar\%\\\\baz")


if __name__ == "__main__":
    unittest.main()
