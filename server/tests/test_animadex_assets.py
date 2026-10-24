from __future__ import annotations

import json
import tempfile
import unittest
from http.client import RemoteDisconnected
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from app import animadex, animadex_assets as assets


WEBP = b'RIFF' + (12).to_bytes(4, 'little') + b'WEBPVP8 ' + b'\0' * 4


class ThumbnailImportTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = patch.dict('os.environ', {'ANIMADEX_DATA_DIR': temporary.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        audit = patch.object(assets, 'record_api_error')
        self.audit = audit.start()
        self.addCleanup(audit.stop)
        config = patch.object(assets, 'settings', SimpleNamespace(auth_secret='synthetic-thumbnail-signing-secret'))
        config.start()
        self.addCleanup(config.stop)
        self.entries = animadex._build_entries([{'character': 'char', 'trigger': 'char: a/b (series)', 'copyright': 'series/a'}], [{'artist': 'artist', 'trigger': 'artist'}])
        self.manifest = {'version': 100, 'r2_base': 'https://blobs.animadex.net', 'prefixes': {'char_thumb': 'Outputs/thumbs', 'artist_thumb': 'ArtistOutputs/thumbs', 'copyright_thumb': 'Outputs/copyrights'}}
        self.index = {'version': 100, 'chars': {'char': 1}, 'artists': {'artist': 0}, 'copyrights': {'series_a.webp': 5}}

    def test_downloads_three_kinds_and_repeat_import_never_fetches_unchanged_files(self):
        fetch = MagicMock(return_value=WEBP)
        result = assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch)
        self.assertEqual(result, {'downloaded': 3, 'unchanged': 0, 'missing': 0, 'failed': 0})
        urls = [call.args[0] for call in fetch.call_args_list]
        self.assertIn('https://blobs.animadex.net/Outputs/thumbs/char_%20a_b%20(series).webp', urls)
        self.assertIn('https://blobs.animadex.net/Outputs/copyrights/series_a.webp', urls)
        for entry in self.entries:
            path = assets.thumbnail_path(entry[0], assets.asset_key(entry[0], entry[1]))
            self.assertEqual(path.read_bytes(), WEBP)
            self.assertNotIn(entry[1], path.name)
        fetch.reset_mock()
        self.assertEqual(assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch)['unchanged'], 3)
        fetch.assert_not_called()

    def test_delta_fetches_changed_version_changed_trigger_and_deleted_file(self):
        fetch = MagicMock(return_value=WEBP)
        assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch)
        self.index['chars']['char'] = 2
        fetch.reset_mock()
        result = assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch)
        self.assertEqual((result['downloaded'], result['unchanged']), (1, 2))
        self.entries[0] = (*self.entries[0][:3], 'new trigger', *self.entries[0][4:])
        assets.thumbnail_path('artists', assets.asset_key('artists', 'artist')).unlink()
        fetch.reset_mock()
        result = assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch)
        self.assertEqual((result['downloaded'], result['unchanged']), (2, 1))
        self.assertTrue(any('new%20trigger.webp' in call.args[0] for call in fetch.call_args_list))

    def test_failed_or_invalid_replacement_preserves_old_file_and_is_retried(self):
        assets.sync_thumbnails(self.entries, self.manifest, self.index, MagicMock(return_value=WEBP))
        self.index['chars']['char'] = 2
        before = assets.read_state()
        result = assets.sync_thumbnails(self.entries, self.manifest, self.index, MagicMock(return_value=b'<html>blocked</html>'))
        self.assertEqual(result['failed'], 1)
        self.assertEqual(assets.read_state(), before)
        self.assertEqual(assets.thumbnail_path('characters', assets.asset_key('characters', 'char')).read_bytes(), WEBP)
        self.audit.assert_called_once()
        result = assets.sync_thumbnails(self.entries, self.manifest, self.index, MagicMock(return_value=WEBP))
        self.assertEqual(result['downloaded'], 1)
        self.assertFalse(list(self.root.rglob('*.part')))

    def test_remote_404_is_counted_as_missing_without_hiding_real_failures(self):
        fetch = MagicMock(side_effect=animadex.CatalogueImportError('missing', status_code=404))
        result = assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch)
        self.assertEqual((result['missing'], result['failed']), (3, 0))
        self.assertEqual(assets.read_state()['assets'], {})
        fetch.side_effect = animadex.CatalogueImportError('unavailable', status_code=503)
        result = assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch)
        self.assertEqual((result['missing'], result['failed']), (0, 3))

    def test_atomic_write_failure_preserves_existing_file_and_cleans_partial_file(self):
        path = self.root / 'existing.webp'
        path.write_bytes(WEBP)
        with patch.object(Path, 'replace', side_effect=OSError('disk full')), self.assertRaises(OSError):
            assets.atomic_write(path, b'replacement')
        self.assertEqual(path.read_bytes(), WEBP)
        self.assertFalse(list(self.root.glob('*.part')))

    def test_untrusted_paths_and_index_shapes_are_rejected(self):
        for bad in [{'r2_base': 'https://evil.example'}, {'r2_base': None}, {'prefixes': {'char_thumb': '../private'}}, {'prefixes': None}, {'version': 200}]:
            with self.subTest(bad=bad), self.assertRaises(assets.AssetSyncError):
                assets.plan_thumbnails(self.entries, {**self.manifest, **bad}, self.index, {})
        with self.assertRaises(assets.AssetSyncError):
            assets.plan_thumbnails(self.entries, self.manifest, {'chars': None}, {})
        for concurrency in [0, 33]:
            fetch = MagicMock()
            with self.assertRaises(assets.AssetSyncError):
                assets.sync_thumbnails(self.entries, self.manifest, self.index, fetch, concurrency=concurrency)
            fetch.assert_not_called()

    def test_only_local_authenticated_thumbnail_path_is_exposed_and_traversal_is_rejected(self):
        self.assertIsNone(assets.thumbnail_url('characters', 'char'))
        assets.sync_thumbnails(self.entries, self.manifest, self.index, MagicMock(return_value=WEBP))
        url = assets.thumbnail_url('characters', 'char')
        self.assertTrue(url.startswith('tags/catalogue/characters/thumbnail/'))
        key = assets.asset_key('characters', 'char')
        response = animadex.local_thumbnail('characters', key, None)
        self.assertEqual(response.media_type, 'image/webp')
        self.assertIn('private', response.headers['cache-control'])
        for key in ['../thumbnails.json', 'a' * 63, 'a' * 64]:
            with self.subTest(key=key), self.assertRaises(HTTPException) as raised:
                animadex.local_thumbnail('characters', key, None)
            self.assertEqual(raised.exception.status_code, 404)

    def test_full_rate_limit_falls_back_to_delta_and_token_never_goes_to_cdn(self):
        manifest = {**self.manifest, 'ok': True, 'index_url': 'https://blobs.animadex.net/export/index.json', 'csv': {'characters': 'https://blobs.animadex.net/export/characters.csv', 'artists': 'https://blobs.animadex.net/export/artists.csv'}}
        chars = b'character,copyright,trigger,core_tags\nchar,series,char,blue eyes\n'
        artists = b'artist\nartist\n'
        responses = [animadex.CatalogueImportError('locked', status_code=429), json.dumps(manifest).encode(), chars, artists, json.dumps(self.index).encode()]
        with patch.dict('os.environ', {'ANIMADEX_EXPORT_TOKEN': 'synthetic-token'}), patch.object(animadex, '_read_url', side_effect=responses) as fetch, patch.object(animadex, 'import_catalogue', return_value={'characters': 1}), patch.object(animadex, 'get_connection') as db, patch.object(animadex, 'sync_thumbnails', return_value={'downloaded': 0, 'unchanged': 0, 'missing': 0, 'failed': 0}):
            animadex.sync_catalogue()
            self.assertEqual(db.return_value.__enter__.return_value.execute.call_args.args[1], (None,))
        self.assertTrue(fetch.call_args_list[0].args[0].endswith('?full=1'))
        self.assertTrue(fetch.call_args_list[1].args[0].endswith('/manifest'))
        for call in fetch.call_args_list[2:]:
            self.assertNotIn('token', call.kwargs)

    def test_parallel_import_is_rejected_before_any_files_are_replaced(self):
        with assets.catalogue_lock():
            with self.assertRaises(assets.AssetSyncError):
                with assets.catalogue_lock():
                    self.fail('Second importer acquired the lock')

    def test_signed_image_url_expires_and_cannot_read_another_file_or_kind(self):
        assets.sync_thumbnails(self.entries, self.manifest, self.index, MagicMock(return_value=WEBP))
        with patch.object(assets.time, 'time', return_value=1000):
            url = assets.thumbnail_url('characters', 'char')
            parsed = urlsplit(url)
            key = assets.asset_key('characters', 'char')
            request = Request({'type': 'http', 'path_params': {'kind': 'characters', 'key': key}, 'query_string': parsed.query.encode()})
            with patch.object(animadex, 'current_user', side_effect=AssertionError('Scoped URL must not require a bearer token')):
                self.assertIsNone(animadex.thumbnail_access(request, None))
            for kind, other_key in [('artists', key), ('characters', 'b' * 64)]:
                request = Request({'type': 'http', 'path_params': {'kind': kind, 'key': other_key}, 'query_string': parsed.query.encode()})
                with self.assertRaises(HTTPException) as raised:
                    animadex.thumbnail_access(request, None)
                self.assertEqual(raised.exception.status_code, 403)
        with patch.object(assets.time, 'time', return_value=2000):
            request = Request({'type': 'http', 'path_params': {'kind': 'characters', 'key': key}, 'query_string': parsed.query.encode()})
            with self.assertRaises(HTTPException) as raised:
                animadex.thumbnail_access(request, None)
            self.assertEqual(raised.exception.status_code, 403)
        request = Request({'type': 'http', 'path_params': {'kind': 'characters', 'key': key}, 'query_string': b''})
        with self.assertRaises(HTTPException) as raised:
            animadex.thumbnail_access(request, None)
        self.assertEqual(raised.exception.status_code, 401)


class ThumbnailConnectionTest(unittest.TestCase):
    def setUp(self):
        for name, value in [('_THUMBNAIL_CONNECTION', SimpleNamespace()), ('record_api_call', MagicMock()), ('record_api_error', MagicMock())]:
            patcher = patch.object(animadex, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_reuses_verified_https_connection_and_never_sends_token_or_follows_redirect(self):
        response = MagicMock(status=200)
        response.read.return_value = WEBP
        with patch.object(animadex, 'HTTPSConnection') as factory:
            connection = factory.return_value
            connection.getresponse.return_value = response
            for _ in range(2):
                self.assertEqual(animadex._read_url('https://blobs.animadex.net/a.webp', resource='thumbnail'), WEBP)
            factory.assert_called_once_with('blobs.animadex.net', timeout=45)
            self.assertEqual(connection.request.call_count, 2)
            self.assertEqual(connection.request.call_args.kwargs['headers'], {'User-Agent': 'LocalField/0.1'})
            response.status = 302
            with self.assertRaises(animadex.CatalogueImportError) as raised:
                animadex._read_url('https://blobs.animadex.net/a.webp', resource='thumbnail')
            self.assertEqual(raised.exception.status_code, 302)
            self.assertEqual(connection.request.call_count, 3)

    def test_expired_connection_reconnects_once_and_404_is_not_retried(self):
        response = MagicMock(status=404)
        response.read.return_value = b'not found'
        stale, fresh = MagicMock(), MagicMock()
        stale.request.side_effect = RemoteDisconnected('closed')
        fresh.getresponse.return_value = response
        with patch.object(animadex, 'HTTPSConnection', side_effect=[stale, fresh]) as factory:
            with self.assertRaises(animadex.CatalogueImportError) as raised:
                animadex._read_url('https://blobs.animadex.net/a.webp', resource='thumbnail')
            self.assertEqual(raised.exception.status_code, 404)
            self.assertEqual(factory.call_count, 2)
            stale.close.assert_called_once()
            fresh.request.assert_called_once()


if __name__ == '__main__':
    unittest.main()
