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
DEFAULT_STORAGE_URL = ""
DEFAULT_STORAGE_API_TOKEN = ""
DEFAULT_CIVITAI_TOKEN = ""
DEFAULT_COMFYUI_MODELS_PATH = "/comfyui-models"
DEFAULT_VLLM_URL = "http://host.docker.internal:30004"
DEFAULT_VLLM_MODEL = "Huihui-Qwen3.8-27B-abliterated-NVFP4"
DEFAULT_EMBEDDING_URL = "http://host.docker.internal:30005"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIMENSIONS = 1024
DEFAULT_DANBOORU_TAGS_PATH = "/app/data/danbooru_tags.csv"
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
    storage_url: str
    storage_api_token: str
    civitai_token: str
    comfyui_models_path: str
    vllm_url: str
    vllm_model: str
    embedding_url: str
    embedding_model: str
    embedding_dimensions: int
    danbooru_tags_path: str

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
            storage_url=os.getenv("STORAGE_URL", DEFAULT_STORAGE_URL),
            storage_api_token=os.getenv("STORAGE_API_TOKEN", DEFAULT_STORAGE_API_TOKEN),
            civitai_token=os.getenv("CIVITAI_TOKEN", DEFAULT_CIVITAI_TOKEN),
            comfyui_models_path=os.getenv("COMFYUI_MODELS_PATH", DEFAULT_COMFYUI_MODELS_PATH),
            vllm_url=os.getenv("VLLM_URL", DEFAULT_VLLM_URL),
            vllm_model=os.getenv("VLLM_MODEL", DEFAULT_VLLM_MODEL),
            embedding_url=os.getenv("EMBEDDING_URL", DEFAULT_EMBEDDING_URL),
            embedding_model=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_EMBEDDING_DIMENSIONS))),
            danbooru_tags_path=os.getenv("DANBOORU_TAGS_PATH", DEFAULT_DANBOORU_TAGS_PATH),
        )


settings = Settings.from_env()
