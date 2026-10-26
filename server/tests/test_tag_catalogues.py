from __future__ import annotations

import io
import json
import unittest
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app import animadex, gelbooru


class CatalogueImportTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        patcher = patch.dict('os.environ', {'ANIMADEX_DATA_DIR': temporary.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        audit = patch.object(animadex, 'record_exception')
        self.import_audit = audit.start()
        self.addCleanup(audit.stop)

    def test_character_artist_and_series_entries_preserve_triggers_and_count_characters(self):
        characters = [{"character": "sample_one", "copyright": "sample_series", "trigger": "sample one, sample series", "core_tags": "blue eyes, long hair", "count": "120"}, {"character": "sample_two", "copyright": "sample_series", "trigger": "sample two, sample series", "core_tags": "red hair", "count": "900"}]
        artists = [{"artist": "sample_artist", "trigger": "artist:sample_artist", "count": "70"}]
        rows = animadex._build_entries(characters, artists)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0][3], "sample one, sample series")
        self.assertEqual(rows[0][4], ["blue eyes", "long hair"])
        series = next(row for row in rows if row[0] == "series")
        self.assertEqual(series[1], "sample_series")
        self.assertEqual(series[7], 2)
        self.assertIn("blue eyes", rows[0][-1])

    def test_empty_or_invalid_snapshot_is_rejected_before_replacement(self):
        with patch("app.animadex.get_connection") as connection:
            for characters, artists in (([], [{"artist": "sample"}]), ([{"character": "sample", "count": "-1"}], [{"artist": "sample"}]), ([{"character": "bad\x00name"}], [{"artist": "sample"}])):
                with self.subTest(characters=characters), self.assertRaises(animadex.CatalogueImportError):
                    animadex._build_entries(characters, artists)
            connection.assert_not_called()

    def test_export_csv_supports_bom_quoted_tags_and_requires_expected_columns(self):
        raw = '\ufeffcharacter,copyright,trigger,core_tags\nchar,series,"char, series","blue eyes, long hair"\n'.encode()
        rows = animadex._csv(raw, {"character", "copyright", "trigger", "core_tags"})
        self.assertEqual(rows[0]["trigger"], "char, series")
        with self.assertRaises(animadex.CatalogueImportError):
            animadex._csv(b"wrong,headers\na,b", {"character"})

    def test_export_token_is_sent_only_to_exact_manifest_host_without_redirects(self):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{}'
        with patch("app.animadex.record_api_call"), patch("app.animadex.record_exception"), patch("app.animadex._OPENER.open") as opener:
            opener.return_value.__enter__.return_value = response
            animadex._read_url("https://animadex.net/api/export/manifest", token="synthetic-token", manifest=True)
            self.assertEqual(opener.call_args.args[0].get_header("X-export-token"), "synthetic-token")
            animadex._read_url("https://blobs.animadex.net/export/characters.csv")
            self.assertIsNone(opener.call_args.args[0].get_header("X-export-token"))
            for url, options in (("https://evil.example/export.csv", {}), ("http://blobs.animadex.net/file", {}), ("https://user@animadex.net/api/export/manifest", {"manifest": True}), ("https://blobs.animadex.net/file", {"token": "synthetic-token"})):
                with self.subTest(url=url), self.assertRaises(animadex.CatalogueImportError):
                    animadex._read_url(url, **options)
            self.assertEqual(opener.call_count, 2)

    def test_cdn_failure_is_reported_without_token_and_does_not_start_live_search(self):
        connection = MagicMock()
        manifest = {"ok": True, "version": 1, "index_url": "https://blobs.animadex.net/export/index.json", "csv": {"characters": "https://blobs.animadex.net/export/characters.csv", "artists": "https://blobs.animadex.net/export/artists.csv"}}
        with patch.dict("os.environ", {"ANIMADEX_EXPORT_TOKEN": "synthetic-private-token"}), patch("app.animadex.get_connection") as db, patch("app.animadex._read_url", side_effect=[json.dumps(manifest).encode(), animadex.CatalogueImportError("CSV TLS connection failed")]) as request:
            db.return_value.__enter__.return_value = connection
            with self.assertRaises(animadex.CatalogueImportError) as raised:
                animadex.sync_catalogue()
            self.assertNotIn("synthetic-private-token", str(raised.exception))
            self.assertEqual(request.call_count, 2)
            self.assertEqual(connection.execute.call_args.args[1], ("CSV TLS connection failed",))
            self.import_audit.assert_called_once()


class LocalSearchTest(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        for module in ("animadex", "gelbooru"):
            patcher = patch(f"app.{module}.get_connection")
            patcher.start().return_value.__enter__.return_value = self.connection
            self.addCleanup(patcher.stop)

    def test_catalogue_search_uses_only_local_db_and_keeps_literal_wildcards(self):
        now = datetime.now(timezone.utc)
        state, count, results = MagicMock(), MagicMock(), MagicMock()
        state.fetchone.return_value = ("snapshot", now, None)
        count.fetchone.return_value = (1,)
        results.fetchall.return_value = [("sample", "Sample", "sample, series", ["blue eyes"], "series", "Series", 10)]
        self.connection.execute.side_effect = [state, count, results]
        with patch("app.animadex._OPENER.open", side_effect=AssertionError("Network is forbidden")) as network:
            result = animadex.search_catalogue("characters", "blue_eyes%", "count", 2, "series")
            network.assert_not_called()
        self.assertEqual(result.source, "local")
        self.assertEqual(result.items[0].trigger, "sample, series")
        parameters = self.connection.execute.call_args.args[1]
        self.assertEqual(parameters, ["characters", "%blue eyes\\%%", "series", 48])

    def test_missing_local_catalogue_reports_saved_import_error(self):
        self.connection.execute.return_value.fetchone.return_value = ("", None, "CSV server TLS unavailable")
        with self.assertRaises(HTTPException) as raised:
            animadex.search_catalogue("artists", "", "count", 1, "")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("TLS", raised.exception.detail)
        self.assertEqual(self.connection.execute.call_count, 1)

    def test_gelbooru_search_is_local_and_category_parameter_is_not_interpolated(self):
        state, count, results = MagicMock(), MagicMock(), MagicMock()
        state.fetchone.return_value = (datetime.now(timezone.utc),)
        count.fetchone.return_value = (1,)
        results.fetchall.return_value = [("sample_tag", 4, 100)]
        self.connection.execute.side_effect = [state, count, results]
        items, total = gelbooru.list_tags("sample tag", 4, "match", 2)
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["aliases"], [])
        self.assertEqual(self.connection.execute.call_args.args[1], ["%sample\\_tag%", 4, "sample_tag", "sample\\_tag%", 50])


if __name__ == "__main__":
    unittest.main()
