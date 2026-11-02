from functools import lru_cache
from typing import Literal

from pydantic import Field
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

    JWT_SECRET: str = "insecure-dev-secret-key-change-in-production-min-32-bytes"
    ACCESS_TOKEN_MINUTES: int = 60
    REFRESH_TOKEN_DAYS: int = 30
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )

    PUSH_BACKEND: str = "null"
    FCM_CREDENTIALS: str = ""

    EMAIL_BACKEND: str = "smtp"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025

    FILE_STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"

    MAP_STYLE_STREETS_URL: str = "https://api.maptiler.com/maps/streets-v2/style.json?key={key}"
    MAP_STYLE_SATELLITE_URL: str = "https://api.maptiler.com/maps/satellite/style.json?key={key}"
    MAP_API_KEY: str = "dev_placeholder_key"

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
