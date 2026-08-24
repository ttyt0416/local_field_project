import os
from dataclasses import dataclass

APP_TITLE = "Local Field Server"
APP_VERSION = "0.1.0"
DEFAULT_APP_ENV = "development"
DEFAULT_SERVER_PORT = 8080
DEFAULT_DB_HOST = "db"
DEFAULT_DB_PORT = 5432
DEFAULT_WEB_LOG_DB_HOST = "web_log_db"
DEFAULT_WEB_LOG_DB_PORT = 5432
DEFAULT_WEB_LOG_POSTGRES_DB = "local_field_web_logs"
DEFAULT_WEB_LOG_POSTGRES_USER = "local_field_web_logs"
DEFAULT_WEB_LOG_POSTGRES_PASSWORD = ""
DEFAULT_AUTH_SECRET = ""
DEFAULT_COMFYUI_URL = "http://host.docker.internal:8188"
HEALTH_STATUS = "ok"


def _cors_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str
    server_port: int
    db_host: str
    db_port: int
    web_log_db_host: str
    web_log_db_port: int
    cors_origins: tuple[str, ...]
    postgres_db: str
    postgres_user: str
    postgres_password: str
    web_log_postgres_db: str
    web_log_postgres_user: str
    web_log_postgres_password: str
    auth_secret: str
    comfyui_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", DEFAULT_APP_ENV),
            server_port=int(os.getenv("SERVER_PORT", str(DEFAULT_SERVER_PORT))),
            db_host=os.getenv("DB_HOST", DEFAULT_DB_HOST),
            db_port=int(os.getenv("DB_PORT", str(DEFAULT_DB_PORT))),
            web_log_db_host=os.getenv("WEB_LOG_DB_HOST", DEFAULT_WEB_LOG_DB_HOST),
            web_log_db_port=int(os.getenv("WEB_LOG_DB_PORT", str(DEFAULT_WEB_LOG_DB_PORT))),
            cors_origins=_cors_origins(os.getenv("CORS_ORIGINS", "")),
            postgres_db=os.getenv("POSTGRES_DB", ""),
            postgres_user=os.getenv("POSTGRES_USER", ""),
            postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
            web_log_postgres_db=os.getenv("WEB_LOG_POSTGRES_DB", DEFAULT_WEB_LOG_POSTGRES_DB),
            web_log_postgres_user=os.getenv("WEB_LOG_POSTGRES_USER", DEFAULT_WEB_LOG_POSTGRES_USER),
            web_log_postgres_password=os.getenv(
                "WEB_LOG_POSTGRES_PASSWORD", DEFAULT_WEB_LOG_POSTGRES_PASSWORD
            ),
            auth_secret=os.getenv("AUTH_SECRET", DEFAULT_AUTH_SECRET),
            comfyui_url=os.getenv("COMFYUI_URL", DEFAULT_COMFYUI_URL),
        )


settings = Settings.from_env()
