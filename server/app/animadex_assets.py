from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from .audit import record_exception
from .configs.constants import settings


class AssetSyncError(ValueError):
    pass


def data_dir() -> Path:
    default = Path(__file__).resolve().parents[2] / '.runtime' / 'tag-catalogues' / 'animadex'
    return Path(os.environ.get('ANIMADEX_DATA_DIR', str(default)))


def asset_key(kind: str, slug: str) -> str:
    return hashlib.sha256(f'{kind}\0{slug}'.encode()).hexdigest()


def thumbnail_path(kind: str, key: str) -> Path:
    return data_dir() / kind / f'{key}.webp'


def thumbnail_url(kind: str, slug: str) -> str | None:
    key = asset_key(kind, slug)
    path = thumbnail_path(kind, key)
    if not path.is_file():
        return None
    expires = int(time.time()) + 900
    signature = _signature(kind, key, expires)
    return f'tags/catalogue/{kind}/thumbnail/{key}?v={path.stat().st_mtime_ns}&expires={expires}&signature={signature}'


def _signature(kind: str, key: str, expires: int) -> str:
    if not settings.auth_secret:
        raise AssetSyncError('서버 인증 키가 설정되지 않았습니다.')
    message = f'animadex-thumbnail\0{kind}\0{key}\0{expires}'.encode()
    return hmac.new(settings.auth_secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(kind: str, key: str, expires: str, signature: str) -> bool:
    try:
        timestamp = int(expires)
        if timestamp < time.time() or timestamp > time.time() + 900 or len(signature) != 64:
            return False
        return hmac.compare_digest(_signature(kind, key, timestamp), signature)
    except (ValueError, TypeError):
        return False


def _filename(value: str) -> str:
    return ''.join('_' if char in '<>:"/\\|?*' else char for char in value).rstrip(' .') or 'unnamed'


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.download-', suffix='.part', delete=False) as output:
            temporary = Path(output.name)
            output.write(raw)
            os.fchmod(output.fileno(), 0o644)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def catalogue_lock():
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.import.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AssetSyncError('AnimaDex 가져오기가 이미 실행 중입니다.') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def read_state() -> dict:
    path = data_dir() / 'thumbnails.json'
    if not path.is_file():
        return {}
    try:
        state = json.loads(path.read_text('utf-8'))
        if isinstance(state, dict) and isinstance(state.get('assets'), dict):
            return state
    except (ValueError, OSError) as exc:
        record_exception(exc, operation="animadex.state.read", context={"path": str(path)})
    return {}


def plan_thumbnails(entries: list[tuple], manifest: dict, index: dict, state: dict) -> tuple[list[dict], int]:
    base = manifest.get('r2_base')
    if not isinstance(base, str) or base.rstrip('/') != 'https://blobs.animadex.net':
        raise AssetSyncError('AnimaDex 썸네일 서버 주소가 올바르지 않습니다.')
    prefixes = manifest.get('prefixes', {})
    if not isinstance(prefixes, dict) or not isinstance(index, dict):
        raise AssetSyncError('AnimaDex 썸네일 인덱스 형식이 올바르지 않습니다.')
    if str(index.get('version')) != str(manifest.get('version')):
        raise AssetSyncError('AnimaDex 카탈로그와 썸네일 인덱스 버전이 다릅니다. 다시 가져와 주세요.')
    groups = {'characters': ('char_thumb', 'chars'), 'artists': ('artist_thumb', 'artists'), 'series': ('copyright_thumb', 'copyrights')}
    jobs = []
    unchanged = 0
    for entry in entries:
        kind, slug, _, trigger = entry[:4]
        prefix_key, index_key = groups[kind]
        prefix = prefixes.get(prefix_key)
        versions = index.get(index_key)
        if not isinstance(prefix, str) or not prefix or any(part in ('', '.', '..') for part in prefix.split('/')) or not isinstance(versions, dict):
            raise AssetSyncError('AnimaDex 썸네일 경로 또는 버전 정보가 올바르지 않습니다.')
        filename = _filename(slug if kind == 'series' else trigger) + '.webp'
        version = versions.get(filename if kind == 'series' else slug, 0)
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise AssetSyncError('AnimaDex 썸네일 버전이 올바르지 않습니다.')
        key = asset_key(kind, slug)
        url = f'https://blobs.animadex.net/{prefix}/{quote(filename, safe="()")}'
        path = thumbnail_path(kind, key)
        previous = state.get('assets', {}).get(key)
        current = {'version': version, 'url': url}
        if previous == current and path.is_file() and path.stat().st_size > 0:
            unchanged += 1
        else:
            jobs.append({'key': key, 'path': path, 'state': current})
    return jobs, unchanged


def sync_thumbnails(entries: list[tuple], manifest: dict, index: dict, fetch: Callable, progress: Callable | None = None, *, concurrency: int = 8) -> dict[str, int]:
    if not 1 <= concurrency <= 32:
        raise AssetSyncError('썸네일 동시 다운로드 수는 1~32여야 합니다.')
    state = read_state()
    jobs, unchanged = plan_thumbnails(entries, manifest, index, state)
    assets = dict(state.get('assets', {}))
    stats = {'downloaded': 0, 'unchanged': unchanged, 'missing': 0, 'failed': 0}

    def download(job):
        try:
            raw = fetch(job['state']['url'], resource='thumbnail')
            if len(raw) < 12 or raw[:4] != b'RIFF' or raw[8:12] != b'WEBP' or int.from_bytes(raw[4:8], 'little') + 8 != len(raw):
                raise AssetSyncError('AnimaDex 썸네일이 올바른 WebP 파일이 아닙니다.')
            atomic_write(job['path'], raw)
            return 'downloaded'
        except ValueError as exc:
            record_exception(exc, operation="animadex.thumbnail", status_code=getattr(exc, 'status_code', 502), context={"path": str(job['path'])})
            return 'missing' if getattr(exc, 'status_code', None) == 404 else 'failed'
        except OSError as exc:
            record_exception(exc, operation="animadex.thumbnail.save", context={"path": str(job['path'])})
            return 'failed'

    def save():
        atomic_write(data_dir() / 'thumbnails.json', json.dumps({'version': manifest['version'], 'assets': assets}, ensure_ascii=False).encode())

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(download, job): job for job in jobs}
        for done, future in enumerate(as_completed(futures), 1):
            job = futures[future]
            outcome = future.result()
            stats[outcome] += 1
            if outcome == 'downloaded':
                assets[job['key']] = job['state']
            if done % 250 == 0 or done == len(jobs):
                save()
                if progress:
                    progress({'completed': done, 'total': len(jobs), **stats})
    save()
    return stats
