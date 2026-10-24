from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, SecretStr

from .auth import UserResponse, current_user
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
    server_configured: bool
    updated_at: datetime | None


def _cipher() -> Fernet:
    if not settings.auth_secret.strip():
        raise CredentialError("토큰 암호화에 필요한 서버 설정이 없습니다.")
    key = hmac.new(settings.auth_secret.encode(), b"local-field:download-tokens:v1", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(user_id: UUID, provider: Provider, token: str) -> str:
    payload = json.dumps({"user_id": str(user_id), "provider": provider, "token": token}).encode()
    return _cipher().encrypt(payload).decode()


def decrypt_token(user_id: UUID, provider: Provider, encrypted: str) -> str:
    try:
        payload = json.loads(_cipher().decrypt(encrypted.encode()))
        if payload["user_id"] != str(user_id) or payload["provider"] != provider or not isinstance(payload["token"], str):
            raise ValueError()
        return payload["token"]
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise CredentialError("저장된 다운로드 토큰을 읽지 못했습니다. 토큰을 다시 저장해 주세요.") from None


def _server_token(provider: Provider) -> str:
    return (settings.civitai_token if provider == "civitai" else settings.hugging_face_token).strip()


def get_effective_token(user_id: UUID | None, provider: Provider) -> str:
    if user_id is not None:
        with get_connection() as connection:
            row = connection.execute("SELECT encrypted_token FROM download_tokens WHERE user_id = %s AND provider = %s", (user_id, provider)).fetchone()
        if row is not None:
            return decrypt_token(user_id, provider, row[0])
    return _server_token(provider)


@router.get("", response_model=list[TokenStatus])
def token_status(user: UserResponse = Depends(current_user)) -> list[TokenStatus]:
    with get_connection() as connection:
        rows = connection.execute("SELECT provider, updated_at FROM download_tokens WHERE user_id = %s", (user.id,)).fetchall()
    saved = dict(rows)
    return [TokenStatus(provider=provider, saved=provider in saved, server_configured=bool(_server_token(provider)), updated_at=saved.get(provider)) for provider in ("civitai", "hugging_face")]


@router.put("/{provider}", response_model=list[TokenStatus])
def save_token(provider: Provider, payload: TokenRequest, user: UserResponse = Depends(current_user)) -> list[TokenStatus]:
    token = payload.token.get_secret_value().strip()
    if not token or len(token) > 4096 or any(not 33 <= ord(char) <= 126 for char in token):
        raise HTTPException(status_code=422, detail="공백 없는 올바른 API 토큰을 입력해 주세요.")
    try:
        encrypted = encrypt_token(user.id, provider, token)
    except CredentialError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    with get_connection() as connection:
        connection.execute("""INSERT INTO download_tokens (user_id, provider, encrypted_token) VALUES (%s, %s, %s)
            ON CONFLICT (user_id, provider) DO UPDATE SET encrypted_token = EXCLUDED.encrypted_token, updated_at = CURRENT_TIMESTAMP""", (user.id, provider, encrypted))
    return token_status(user)


@router.delete("/{provider}", response_model=list[TokenStatus])
def remove_token(provider: Provider, user: UserResponse = Depends(current_user)) -> list[TokenStatus]:
    with get_connection() as connection:
        connection.execute("DELETE FROM download_tokens WHERE user_id = %s AND provider = %s", (user.id, provider))
    return token_status(user)
