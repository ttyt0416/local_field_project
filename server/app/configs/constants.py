import os
from dataclasses import dataclass

APP_TITLE = "Local Field Server"
APP_VERSION = "0.1.0"
DEFAULT_APP_ENV = "development"
DEFAULT_SERVER_PORT = 8080
DEFAULT_DB_HOST = "db"
DEFAULT_DB_PORT = 5432
DEFAULT_AUTH_SECRET = ""
HEALTH_STATUS = "ok"


def _cors_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str
    server_port: int
    db_host: str
    db_port: int
    cors_origins: tuple[str, ...]
    postgres_db: str
    postgres_user: str
    postgres_password: str
    auth_secret: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", DEFAULT_APP_ENV),
            server_port=int(os.getenv("SERVER_PORT", str(DEFAULT_SERVER_PORT))),
            db_host=os.getenv("DB_HOST", DEFAULT_DB_HOST),
            db_port=int(os.getenv("DB_PORT", str(DEFAULT_DB_PORT))),
            cors_origins=_cors_origins(os.getenv("CORS_ORIGINS", "")),
            postgres_db=os.getenv("POSTGRES_DB", ""),
            postgres_user=os.getenv("POSTGRES_USER", ""),
            postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
            auth_secret=os.getenv("AUTH_SECRET", DEFAULT_AUTH_SECRET),
        )


settings = Settings.from_env()
