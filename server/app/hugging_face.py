from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlparse
from urllib.request import Request


class HuggingFaceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class HuggingFaceSource:
    repo_id: str
    revision: str
    path: str = ""
    is_file: bool = False


@dataclass(frozen=True)
class HuggingFaceFile:
    path: str
    size_bytes: int | None
    sha256: str | None


@dataclass(frozen=True)
class HuggingFaceRepository:
    repo_id: str
    revision: str
    files: tuple[HuggingFaceFile, ...]


def safe_repo_id(value: str) -> str:
    parts = value.split("/")
    if len(value) > 200 or len(parts) not in {1, 2} or parts[0] in {"datasets", "spaces", "docs", "api", "settings"}:
        raise HuggingFaceError("Hugging Face 모델 저장소 주소 또는 owner/repo를 입력해 주세요.", 422)
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) or ".." in part or "--" in part or part.endswith(".git") for part in parts):
        raise HuggingFaceError("Hugging Face 저장소 이름이 올바르지 않습니다.", 422)
    return value


def safe_revision(value: str, *, pinned: bool = False) -> str:
    if pinned:
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise HuggingFaceError("Hugging Face 리비전 정보가 올바르지 않습니다.", 422)
    elif not value or len(value) > 200 or "\\" in value or any(ord(char) < 32 for char in value) or any(part in {"", ".", ".."} for part in value.split("/")):
        raise HuggingFaceError("리비전 이름이 올바르지 않습니다.", 422)
    return value


def safe_repo_path(value: str) -> str:
    if not value or len(value.encode("utf-8")) > 1024 or value.startswith("/") or "\\" in value or any(ord(char) < 32 for char in value) or any(part in {"", ".", ".."} for part in value.split("/")):
        raise HuggingFaceError("Hugging Face 파일 경로가 올바르지 않습니다.", 422)
    if len(PurePosixPath(value).name.encode("utf-8")) > 255:
        raise HuggingFaceError("파일 이름이 너무 깁니다.", 422)
    return value


def parse_source(raw_source: str, revision: str = "") -> HuggingFaceSource:
    source = raw_source.strip()
    if "://" not in source:
        return HuggingFaceSource(safe_repo_id(source), safe_revision(revision.strip() or "main"))
    parsed = urlparse(source)
    if parsed.scheme != "https" or parsed.netloc.lower() != "huggingface.co" or any(ord(char) < 32 for char in source):
        raise HuggingFaceError("https://huggingface.co 모델 저장소 또는 파일 링크를 입력해 주세요.", 422)
    parts = parsed.path.strip("/").split("/")
    marker = next((index for index, part in enumerate(parts) if part in {"blob", "resolve", "tree"} and index in {1, 2} and len(parts) > index + 1), None)
    if marker is None:
        return HuggingFaceSource(safe_repo_id(unquote("/".join(parts))), safe_revision(revision.strip() or "main"))
    if len(parts) < marker + 2:
        raise HuggingFaceError("Hugging Face 링크에 리비전이 없습니다.", 422)
    repo_id = safe_repo_id(unquote("/".join(parts[:marker])))
    branch = safe_revision(revision.strip() or unquote(parts[marker + 1]))
    path = unquote("/".join(parts[marker + 2:]))
    is_file = parts[marker] in {"blob", "resolve"}
    if path:
        safe_repo_path(path)
    elif is_file:
        raise HuggingFaceError("Hugging Face 파일 링크에 파일 경로가 없습니다.", 422)
    return HuggingFaceSource(repo_id, branch, path, is_file)


def open_download(url: str, token: str, resume_from: int, opener: Any):
    current = url
    for hop in range(6):
        parsed = urlparse(current)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.netloc.lower() != host or not (host == "huggingface.co" or host.endswith(".hf.co") or host.endswith(".huggingface.co")) or (hop == 0 and host != "huggingface.co"):
            raise HuggingFaceError("Hugging Face 다운로드 주소가 올바르지 않습니다.")
        headers = {"User-Agent": "LocalField/0.1"}
        if token and host == "huggingface.co":
            headers["Authorization"] = f"Bearer {token}"
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
        try:
            return opener.open(Request(current, headers=headers), timeout=60)
        except HTTPError as exc:
            code = exc.code
            location = exc.headers.get("Location")
            exc.close()
            if code in {301, 302, 303, 307, 308} and location:
                current = urljoin(current, location)
                continue
            if code in {401, 403}:
                raise HuggingFaceError("Hugging Face 접근 권한이 없습니다. 비공개·제한 모델은 서버 HF_TOKEN과 저장소 접근 승인을 확인해 주세요.", 403) from exc
            if code == 404:
                raise HuggingFaceError("Hugging Face 저장소·리비전 또는 파일을 찾을 수 없습니다.", 404) from exc
            if code == 429:
                raise HuggingFaceError("Hugging Face 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.", 429) from exc
            raise HuggingFaceError("Hugging Face에서 파일 정보를 받지 못했습니다.") from exc
        except (URLError, TimeoutError, OSError):
            raise HuggingFaceError("Hugging Face에 연결할 수 없습니다.") from None
    raise HuggingFaceError("Hugging Face 리디렉션이 너무 많습니다.")


def fetch_repository(repo_id: str, revision: str, token: str, opener: Any, extensions: set[str]) -> HuggingFaceRepository:
    repo_id = safe_repo_id(repo_id)
    revision = safe_revision(revision)
    url = f"https://huggingface.co/api/models/{quote(repo_id, safe='/')}/revision/{quote(revision, safe='')}?blobs=true"
    try:
        with open_download(url, token, 0, opener) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise HuggingFaceError("저장소 파일 목록이 너무 큽니다. 더 작은 저장소를 선택해 주세요.")
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise HuggingFaceError("Hugging Face 파일 목록 형식이 올바르지 않습니다.") from None
    except (OSError, TimeoutError):
        raise HuggingFaceError("Hugging Face 파일 목록을 끝까지 받지 못했습니다. 다시 시도해 주세요.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("siblings"), list):
        raise HuggingFaceError("Hugging Face 파일 목록을 확인할 수 없습니다.")
    commit = payload.get("sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise HuggingFaceError("Hugging Face 커밋 정보를 확인할 수 없습니다.")
    if re.fullmatch(r"[0-9a-f]{40}", revision) and revision != commit:
        raise HuggingFaceError("요청한 리비전과 응답 커밋이 다릅니다.")
    files = []
    for entry in payload["siblings"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("rfilename"), str):
            continue
        path = entry["rfilename"]
        if PurePosixPath(path).suffix.lower() not in extensions:
            continue
        try:
            safe_repo_path(path)
        except HuggingFaceError:
            continue
        lfs = entry.get("lfs") if isinstance(entry.get("lfs"), dict) else {}
        size = lfs.get("size", entry.get("size"))
        size = size if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else None
        sha = lfs.get("sha256")
        sha = sha.lower() if isinstance(sha, str) and re.fullmatch(r"[0-9a-fA-F]{64}", sha) else None
        files.append(HuggingFaceFile(path, size, sha))
    return HuggingFaceRepository(repo_id, commit, tuple(sorted(files, key=lambda file: file.path.lower())))


def file_url(repo_id: str, revision: str, path: str) -> str:
    repo_id = safe_repo_id(repo_id)
    revision = safe_revision(revision, pinned=True)
    path = safe_repo_path(path)
    return f"https://huggingface.co/{quote(repo_id, safe='/')}/resolve/{revision}/{quote(path, safe='/')}"
