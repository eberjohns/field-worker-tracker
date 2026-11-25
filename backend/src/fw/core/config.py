from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["local", "staging", "production"] = "local"
    DEPLOYMENT_COUNTRY: Literal["AE", "SA"] = "AE"

    DATABASE_URL: str = "postgresql+asyncpg://fw_app:fw_secret@localhost:5432/fw_db"
    DATABASE_MIGRATOR_URL: str = (
        "postgresql+asyncpg://fw_migrator:fw_migrator_secret@localhost:5432/fw_db"
    )

    @field_validator("DATABASE_URL", "DATABASE_MIGRATOR_URL", mode="before")
    @classmethod
    def normalize_database_urls(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            if v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    JWT_SECRET: str = "insecure-dev-secret-key-change-in-production-min-32-bytes"
    ACCESS_TOKEN_MINUTES: int = 60
    REFRESH_TOKEN_DAYS: int = 30
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8085",
            "http://127.0.0.1:8085",
            "http://localhost:4173",
        ]
    )

    FILE_STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"
    ARCHIVE_STORAGE_PATH: str = "./storage/archives"
    ARCHIVE_ENCRYPTION_KEY: str = "insecure-dev-archive-encryption-key-min-32-chars-ok"
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_LOGIN_WINDOW_MINUTES: int = 15

    LOG_LEVEL: str = "INFO"

    # Speed measuring (Batch 9): Server-Timing header and a request_timing log line per request.
    # Dev and staging only; ignored when APP_ENV is production (fw/core/perf.py).
    PERF_TIMING_ENABLED: bool = False
    PERF_SLOW_QUERY_MS: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
