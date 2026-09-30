from functools import lru_cache
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application configuration.
    Loads settings from environment variables and optionally from .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    APP_ENV: str = "development"
    APP_NAME: str = "AI-Driven Intelligent UFDR Analysis System"
    APP_VERSION: str = "0.2.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS configuration - default to standard local Vite and React ports
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Security & JWT Configuration
    JWT_SECRET: str = "dev_secret_replace_in_production_with_high_entropy_key_min_32_chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database Configuration
    # Defaults to SQLite async for seamless zero-setup local dev/tests, easily overridden by PostgreSQL URL
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/ufdr_forensics.db"
    MONGODB_URI: str = "mongodb://localhost:27017/ufdr_raw_artifacts"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Evidence & Storage Roots
    EVIDENCE_STORAGE_PATH: str = "./storage/evidence"
    SCRATCH_STORAGE_PATH: str = "./storage/scratch"

    # Bootstrap Initial Admin (Configured via environment variables)
    INITIAL_ADMIN_EMAIL: str = "admin@ufdr.org"
    INITIAL_ADMIN_PASSWORD: str = "ForensicAdmin2026!"
    INITIAL_ADMIN_NAME: str = "Forensic System Administrator"

    # Brute Force Protection
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError("Invalid format for CORS_ORIGINS")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
