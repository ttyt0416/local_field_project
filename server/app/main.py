from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .configs.constants import HEALTH_STATUS, APP_TITLE, APP_VERSION, settings

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": HEALTH_STATUS}
