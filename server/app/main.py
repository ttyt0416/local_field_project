from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .configs.constants import APP_TITLE, APP_VERSION, HEALTH_STATUS, settings
from .database import initialize_database, record_api_call, record_api_error


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
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
