import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation

from .configs.constants import settings
from .database import get_connection, record_auth_event


router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)
_USERNAME_PATTERN = re.compile(r"^\S+$")
_PASSWORD_SCRYPT_N = 2**14
_PASSWORD_SCRYPT_R = 8
_PASSWORD_SCRYPT_P = 1
_JWT_ALGORITHM = "HS256"
_JWT_TTL = timedelta(days=7)


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request) -> AuthResponse:
    username = _normalize_username(payload.username)
    try:
        _validate_username(username)
    except HTTPException:
        _record_auth_event(request, "signup", username, False, "invalid_username")
        raise
    user_id = uuid.uuid4()

    try:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (%s, %s, %s)",
                (user_id, username, _hash_password(payload.password)),
            )
    except UniqueViolation as exc:
        _record_auth_event(request, "signup", username, False, "duplicate_username")
        raise HTTPException(status_code=409, detail="이미 가입된 아이디입니다.") from exc

    _record_auth_event(request, "signup", username, True, user_id=user_id)
    request.state.user_id = user_id
    return _auth_response(user_id, username)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request) -> AuthResponse:
    username = _normalize_username(payload.username)
    try:
        _validate_username(username)
    except HTTPException:
        _record_auth_event(request, "login", username, False, "invalid_username")
        raise

    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = %s",
            (username,),
        ).fetchone()
        if row is None or not _verify_password(payload.password, row[1]):
            _record_auth_event(
                request,
                "login",
                username,
                False,
                "invalid_credentials",
                user_id=row[0] if row else None,
            )
            raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    user_id = row[0]
    _record_auth_event(request, "login", username, True, user_id=user_id)
    request.state.user_id = user_id
    return _auth_response(user_id, username)


@router.get("/me", response_model=UserResponse)
def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    user_id, username = _decode_access_token(credentials.credentials)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()

    if row is None:
        raise _unauthorized()

    request.state.user_id = row[0]
    return UserResponse(id=row[0], username=row[1])


def _auth_response(user_id: uuid.UUID, username: str) -> AuthResponse:
    return AuthResponse(
        access_token=_create_access_token(user_id, username),
        token_type="bearer",
        user=UserResponse(id=user_id, username=username),
    )


def _record_auth_event(
    request: Request,
    event_type: str,
    username: str | None,
    success: bool,
    failure_reason: str | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    record_auth_event(
        event_type=event_type,
        username=username,
        success=success,
        failure_reason=failure_reason,
        client_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        user_id=user_id,
    )


def _client_ip(request: Request) -> str | None:
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            return value.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _validate_username(username: str) -> None:
    if not 3 <= len(username) <= 32 or not _USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(status_code=422, detail="올바른 아이디를 입력해 주세요.")


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_PASSWORD_SCRYPT_N,
        r=_PASSWORD_SCRYPT_R,
        p=_PASSWORD_SCRYPT_P,
    )
    return f"scrypt${_PASSWORD_SCRYPT_N}${_PASSWORD_SCRYPT_R}${_PASSWORD_SCRYPT_P}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def _create_access_token(user_id: uuid.UUID, username: str) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + _JWT_TTL).timestamp()),
    }
    return _encode_jwt(payload)


def _encode_jwt(payload: dict[str, object]) -> str:
    header = {"alg": _JWT_ALGORITHM, "typ": "JWT"}
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(_jwt_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _decode_access_token(token: str) -> tuple[uuid.UUID, str]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            _jwt_secret(), signing_input.encode("ascii"), hashlib.sha256
        ).digest()
        actual_signature = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise _unauthorized()

        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        if header.get("alg") != _JWT_ALGORITHM or header.get("typ") != "JWT":
            raise _unauthorized()

        expires_at = int(payload["exp"])
        if datetime.now(timezone.utc).timestamp() >= expires_at:
            raise _unauthorized()
        return uuid.UUID(str(payload["sub"])), str(payload["username"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise _unauthorized()


def _jwt_secret() -> bytes:
    if not settings.auth_secret:
        raise RuntimeError("AUTH_SECRET must be configured")
    return settings.auth_secret.encode("utf-8")


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
