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
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PASSWORD_SCRYPT_N = 2**14
_PASSWORD_SCRYPT_R = 8
_PASSWORD_SCRYPT_P = 1
_JWT_ALGORITHM = "HS256"
_JWT_TTL = timedelta(days=7)


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request) -> AuthResponse:
    email = _normalize_email(payload.email)
    try:
        _validate_email(email)
    except HTTPException:
        _record_auth_event(request, "signup", email, False, "invalid_email")
        raise
    user_id = uuid.uuid4()

    try:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
                (user_id, email, _hash_password(payload.password)),
            )
    except UniqueViolation as exc:
        _record_auth_event(request, "signup", email, False, "duplicate_email")
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.") from exc

    _record_auth_event(request, "signup", email, True, user_id=user_id)
    request.state.user_id = user_id
    return _auth_response(user_id, email)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request) -> AuthResponse:
    email = _normalize_email(payload.email)
    try:
        _validate_email(email)
    except HTTPException:
        _record_auth_event(request, "login", email, False, "invalid_email")
        raise

    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, password_hash FROM users WHERE email = %s",
            (email,),
        ).fetchone()
        if row is None or not _verify_password(payload.password, row[1]):
            _record_auth_event(
                request,
                "login",
                email,
                False,
                "invalid_credentials",
                user_id=row[0] if row else None,
            )
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    user_id = row[0]
    _record_auth_event(request, "login", email, True, user_id=user_id)
    request.state.user_id = user_id
    return _auth_response(user_id, email)


@router.get("/me", response_model=UserResponse)
def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    user_id, email = _decode_access_token(credentials.credentials)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, email FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()

    if row is None:
        raise _unauthorized()

    request.state.user_id = row[0]
    return UserResponse(id=row[0], email=row[1])


def _auth_response(user_id: uuid.UUID, email: str) -> AuthResponse:
    return AuthResponse(
        access_token=_create_access_token(user_id, email),
        token_type="bearer",
        user=UserResponse(id=user_id, email=email),
    )


def _record_auth_event(
    request: Request,
    event_type: str,
    email: str | None,
    success: bool,
    failure_reason: str | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    record_auth_event(
        event_type=event_type,
        email=email,
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


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_email(email: str) -> None:
    if not _EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="올바른 이메일 주소를 입력해 주세요.")


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


def _create_access_token(user_id: uuid.UUID, email: str) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
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
        return uuid.UUID(str(payload["sub"])), str(payload["email"])
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
