from contextlib import asynccontextmanager
import asyncio
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import _decode_access_token, router as auth_router
from .audit import audit_error_response, record_exception, request_context
from .comfyui import router as comfyui_router
from .configs.constants import APP_TITLE, APP_VERSION, HEALTH_STATUS, settings
from .database import initialize_database, record_api_call, record_api_error, record_web_event
from .danbooru import router as danbooru_router
from .animadex import router as animadex_router
from .gelbooru import router as gelbooru_router
from .download_tokens import router as download_tokens_router
from .saved_prompts import router as saved_prompts_router
from .latency import ApiTimingMiddleware
from .generation_worker import run_generation_reconciler
from .generations import router as generations_router
from .hardware import router as hardware_router
from .model_downloads import router as model_downloads_router, run_model_download_worker
from .music import router as music_router
from .presets import router as presets_router
from .three_d import router as three_d_router
from .rigging import router as rigging_router
from .uploads import router as uploads_router
from .vault import router as vault_router
from .video import router as video_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    stop_event = asyncio.Event()
    reconciler = asyncio.create_task(run_generation_reconciler(stop_event))
    model_downloader = asyncio.create_task(run_model_download_worker(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await asyncio.gather(reconciler, model_downloader)


app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


class WebEventRequest(BaseModel):
    event_type: Literal["click", "route", "pointerdown", "change", "submit", "keyboard", "media"]
    page_path: str = Field(min_length=1, max_length=65536)
    from_path: str | None = Field(default=None, max_length=65536)
    target_type: str = Field(min_length=1, max_length=32)
    target_id: str | None = Field(default=None, max_length=65536)
    target_label: str | None = Field(default=None, max_length=512)
    target_href: str | None = Field(default=None, max_length=65536)
    event_id: uuid.UUID | None = None
    client_occurred_at: datetime | None = None
    visitor_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    target_path: str | None = Field(default=None, max_length=65536)
    target_context: dict[str, Any] = Field(default_factory=dict)


def telemetry_user(request: Request) -> uuid.UUID | None:
    try:
        scheme, token = request.headers.get("authorization", "").split(" ", 1)
        if scheme.lower() != "bearer":
            return None
        user_id, _ = _decode_access_token(token)
        request.state.user_id = user_id
        return user_id
    except Exception:
        return None


@app.post("/web/events", status_code=204)
def web_event(
    payload: WebEventRequest,
    request: Request,
    user_id: uuid.UUID | None = Depends(telemetry_user),
) -> None:
    client_ip = request.client.host if request.client else None
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            client_ip = value.split(",", 1)[0].strip()
            break
    record_web_event(
        event_type=payload.event_type,
        page_path=payload.page_path,
        from_path=payload.from_path,
        target_type=payload.target_type,
        target_id=payload.target_id,
        target_label=payload.target_label,
        target_href=payload.target_href,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        user_id=user_id,
        event_id=payload.event_id,
        client_occurred_at=payload.client_occurred_at,
        visitor_id=payload.visitor_id,
        session_id=payload.session_id,
        target_path=payload.target_path,
        target_context=payload.target_context,
    )


class ClientApiError(BaseModel):
    page_path: str
    api_path: str
    method: str
    error_type: str
    error_message: str
    stack: str | None = None
    response: Any = None
    status_code: int = Field(default=0, ge=0, le=599)
    client_occurred_at: datetime | None = None


@app.post("/web/errors", status_code=204)
def client_api_error(payload: ClientApiError, request: Request,
                     user_id: uuid.UUID | None = Depends(telemetry_user)) -> None:
    record_api_error(method=payload.method, path=payload.api_path,
                     status_code=payload.status_code, error_type=payload.error_type,
                     error_message=payload.error_message, client_ip=request.client.host if request.client else None,
                     user_agent=request.headers.get("user-agent"), user_id=user_id,
                     error_details={"source": "browser", **payload.model_dump(mode="json")})


class ClientApiTiming(BaseModel):
    request_id: uuid.UUID
    method: str = Field(min_length=1, max_length=16)
    api_path: str = Field(min_length=1, max_length=65536)
    page_path: str = Field(max_length=65536)
    requested_at: datetime
    finished_at: datetime | None = None
    headers_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    first_byte_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    duration_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    status_code: int = Field(default=0, ge=0, le=599)
    outcome: Literal["in_progress", "completed", "http_error", "error", "cancelled", "timeout"]
    visitor_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None


@app.post("/web/api-timings", status_code=204)
def client_api_timing(payload: ClientApiTiming, request: Request,
                      user_id: uuid.UUID | None = Depends(telemetry_user)) -> None:
    record_api_call(method=payload.method, path=payload.api_path, status_code=payload.status_code,
                    client_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"), user_id=user_id,
                    source="browser", request_id=payload.request_id, requested_at=payload.requested_at,
                    finished_at=payload.finished_at, headers_ms=payload.headers_ms,
                    first_byte_ms=payload.first_byte_ms, duration_ms=payload.duration_ms,
                    outcome=payload.outcome,
                    timing_context={"page_path": payload.page_path, "visitor_id": payload.visitor_id,
                                    "session_id": payload.session_id})


@app.exception_handler(StarletteHTTPException)
async def audit_handled_exception(request: Request, error: StarletteHTTPException):
    request.state.audit_error = error
    return await http_exception_handler(request, error)


@app.exception_handler(RequestValidationError)
async def audit_validation_exception(request: Request, error: RequestValidationError):
    request.state.audit_error = error
    return await request_validation_exception_handler(request, error)


@app.middleware("http")
async def audit_api_requests(request: Request, call_next: Any):
    response = None
    raised_error: Exception | None = None
    metadata = {
        "method": request.method, "path": request.url.path,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"), "user_id": telemetry_user(request),
        "request_id": getattr(request.state, "api_request_id", None),
    }
    context_token = request_context.set(metadata)
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        raised_error = exc
        raise
    finally:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        user_id = getattr(request.state, "user_id", None)
        provider_response = getattr(request.state, "provider_response", None)
        if not isinstance(provider_response, dict):
            provider_response = None
        status_code = response.status_code if response is not None else 500

        error = raised_error or getattr(request.state, "audit_error", None)
        if error is not None:
            record_exception(error, status_code=status_code, user_id=user_id,
                             operation="http.request", provider_response=provider_response)
        elif status_code >= 400:
            audit_error_response(
                response,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                client_ip=client_ip,
                user_agent=user_agent,
                user_id=user_id,
                provider_response=provider_response,
            )

        request_context.reset(context_token)


app.add_middleware(ApiTimingMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": HEALTH_STATUS}


app.include_router(auth_router)
app.include_router(comfyui_router)
app.include_router(danbooru_router)
app.include_router(animadex_router)
app.include_router(gelbooru_router)
app.include_router(download_tokens_router)
app.include_router(saved_prompts_router)
app.include_router(generations_router)
app.include_router(hardware_router)
app.include_router(model_downloads_router)
app.include_router(music_router)
app.include_router(presets_router)
app.include_router(rigging_router)
app.include_router(three_d_router)
app.include_router(uploads_router)
app.include_router(vault_router)
app.include_router(video_router)
