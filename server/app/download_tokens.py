from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, SecretStr

from .configs.constants import settings
from .database import get_connection


Provider = Literal["civitai", "hugging_face"]
router = APIRouter(prefix="/models/tokens", tags=["download tokens"])


class CredentialError(ValueError):
    pass


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr


class TokenStatus(BaseModel):
    provider: Provider
    saved: bool
    updated_at: datetime | None


def _cipher() -> Fernet:
    if not settings.token_encryption_secret.strip():
        raise CredentialError("토큰 암호화에 필요한 서버 설정이 없습니다.")
    key = hmac.new(settings.token_encryption_secret.encode(), b"local-field:download-tokens:v1", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(provider: Provider, token: str) -> str:
    payload = json.dumps({"provider": provider, "token": token}).encode()
    return _cipher().encrypt(payload).decode()


def decrypt_token(provider: Provider, encrypted: str) -> str:
    try:
        payload = json.loads(_cipher().decrypt(encrypted.encode()))
        if payload["provider"] != provider or not isinstance(payload["token"], str):
            raise ValueError()
        return payload["token"]
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise CredentialError("저장된 다운로드 토큰을 읽지 못했습니다. 토큰을 다시 저장해 주세요.") from None


def get_effective_token(provider: Provider) -> str:
    with get_connection() as connection:
        row = connection.execute("SELECT encrypted_token FROM download_tokens WHERE provider = %s", (provider,)).fetchone()
    return decrypt_token(provider, row[0]) if row is not None else ""


@router.get("", response_model=list[TokenStatus])
def token_status() -> list[TokenStatus]:
    with get_connection() as connection:
        rows = connection.execute("SELECT provider, updated_at FROM download_tokens").fetchall()
    saved = dict(rows)
    return [TokenStatus(provider=provider, saved=provider in saved, updated_at=saved.get(provider)) for provider in ("civitai", "hugging_face")]


@router.put("/{provider}", response_model=list[TokenStatus])
def save_token(provider: Provider, payload: TokenRequest) -> list[TokenStatus]:
    token = payload.token.get_secret_value().strip()
    if not token or len(token) > 4096 or any(not 33 <= ord(char) <= 126 for char in token):
        raise HTTPException(status_code=422, detail="공백 없는 올바른 API 토큰을 입력해 주세요.")
    try:
        encrypted = encrypt_token(provider, token)
    except CredentialError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    with get_connection() as connection:
        connection.execute("""INSERT INTO download_tokens (provider, encrypted_token) VALUES (%s, %s)
            ON CONFLICT (provider) DO UPDATE SET encrypted_token = EXCLUDED.encrypted_token, updated_at = CURRENT_TIMESTAMP""", (provider, encrypted))
    return token_status()


@router.delete("/{provider}", response_model=list[TokenStatus])
def remove_token(provider: Provider) -> list[TokenStatus]:
    with get_connection() as connection:
        connection.execute("DELETE FROM download_tokens WHERE provider = %s", (provider,))
    return token_status()
