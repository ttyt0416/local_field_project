from contextlib import asynccontextmanager
import asyncio
import uuid
from typing import Any, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth import optional_user_id, router as auth_router
from .comfyui import router as comfyui_router
from .configs.constants import APP_TITLE, APP_VERSION, HEALTH_STATUS, settings
from .database import initialize_database, record_api_call, record_api_error, record_web_event
from .danbooru import router as danbooru_router
from .generation_worker import run_generation_reconciler
from .generations import router as generations_router
from .model_downloads import router as model_downloads_router, run_model_download_worker
from .presets import router as presets_router
from .three_d import router as three_d_router
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
    event_type: Literal["click", "route"]
    page_path: str = Field(min_length=1, max_length=2048)
    from_path: str | None = Field(default=None, max_length=2048)
    target_type: str = Field(min_length=1, max_length=32)
    target_id: str | None = Field(default=None, max_length=255)
    target_label: str | None = Field(default=None, max_length=512)
    target_href: str | None = Field(default=None, max_length=2048)


@app.post("/web/events", status_code=204)
def web_event(
    payload: WebEventRequest,
    request: Request,
    user_id: uuid.UUID | None = Depends(optional_user_id),
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
    )


@app.middleware("http")
async def audit_api_requests(request: Request, call_next: Any):
    response = None
    raised_error: Exception | None = None
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
        status_code = response.status_code if response is not None else 500

        if raised_error is not None:
            record_api_error(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                error_type=type(raised_error).__name__,
                error_message=str(raised_error),
                client_ip=client_ip,
                user_agent=user_agent,
                user_id=user_id,
            )
        elif status_code >= 400:
            record_api_error(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                error_type="HTTPError",
                error_message=f"HTTP {status_code}",
                client_ip=client_ip,
                user_agent=user_agent,
                user_id=user_id,
            )

        record_api_call(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            client_ip=client_ip,
            user_agent=user_agent,
            user_id=user_id,
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": HEALTH_STATUS}


app.include_router(auth_router)
app.include_router(comfyui_router)
app.include_router(danbooru_router)
app.include_router(generations_router)
app.include_router(model_downloads_router)
app.include_router(presets_router)
app.include_router(three_d_router)
app.include_router(uploads_router)
app.include_router(vault_router)
app.include_router(video_router)
