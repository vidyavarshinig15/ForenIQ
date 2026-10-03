from functools import lru_cache
from typing import List, Optional, Union
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
    MAX_UPLOAD_SIZE_MB: int = 1024  # 1 GB default upload size limit
    ALLOWED_EVIDENCE_EXTENSIONS: List[str] = [".ufdr", ".zip"]
    STORAGE_BACKEND: str = "local"

    # UFDR Archive & Extraction Safety Limits (ZipBomb / Resource Exhaustion)
    MAX_ARCHIVE_ENTRIES: int = 50000
    MAX_TOTAL_UNCOMPRESSED_SIZE_MB: int = 10240  # 10 GB uncompressed limit
    MAX_SINGLE_ENTRY_SIZE_MB: int = 2048  # 2 GB single entry limit
    MAX_COMPRESSION_RATIO: float = 100.0  # Max 100:1 ratio before triggering ZipBomb alert
    MAX_ARCHIVE_DEPTH: int = 2  # Max nesting levels allowed
    MAX_TEMP_STORAGE_MB: int = 20480  # 20 GB scratch storage limit

    # Phase 6: Queue & Worker Governance Settings
    QUEUE_BACKEND: str = "auto"  # "auto", "redis", or "database"
    WORKER_CONCURRENCY: int = 2  # Bounded worker concurrency
    MAX_WORKERS: int = 4
    MAX_CONCURRENT_JOBS: int = 4
    PARSER_BATCH_SIZE: int = 500  # Database insert batch size
    JOB_HEARTBEAT_INTERVAL_SECONDS: int = 5
    JOB_LEASE_TIMEOUT_SECONDS: int = 30  # Stale job detection threshold
    MAX_JOB_RETRIES: int = 3
    JOB_RETRY_BACKOFF_BASE_SECONDS: float = 2.0

    # Phase 10: Semantic Retrieval & Embedding Configuration
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_MODEL_VERSION: str = "2.0.0"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 64
    EMBEDDING_DEVICE: str = "cpu"  # "cpu", "cuda", "mps"
    VECTOR_INDEX_DIR: str = "./storage/vector_indices"
    MAX_SEMANTIC_TOP_K: int = 100
    DEFAULT_SEMANTIC_WEIGHT: float = 0.5
    DEFAULT_LEXICAL_WEIGHT: float = 0.5
    EXACT_MATCH_BOOST: float = 0.3

    # Phase 11: NLP Query Understanding & Investigation Intent
    SPACY_MODEL_NAME: str = "en_core_web_sm"
    NLP_PARSER_VERSION: str = "1.0.0"
    MAX_INVESTIGATION_QUERY_LENGTH: int = 500
    DEFAULT_INVESTIGATION_TOP_K: int = 50

    # Phase 12: Retrieval-Augmented Generation (RAG) & Forensic Assistant
    RAG_LLM_PROVIDER: str = "local"  # "local", "openai_compatible", "mock"
    RAG_LLM_MODEL: str = "deterministic-forensic-rag-v1"
    RAG_OPENAI_BASE_URL: Optional[str] = None
    RAG_OPENAI_API_KEY: Optional[str] = None
    RAG_TEMPERATURE: float = 0.0
    RAG_MAX_CONTEXT_RECORDS: int = 15
    RAG_MAX_CONTEXT_TOKENS: int = 3000
    RAG_MAX_OUTPUT_TOKENS: int = 800
    RAG_VERSION: str = "1.0.0"
    RAG_ALLOW_EXTERNAL_APIS: bool = False  # Strict privacy boundary

    # Phase 13: Communication Graph Analysis & Social Network Analytics
    GRAPH_MAX_NODES: int = 1000
    GRAPH_MAX_EDGES: int = 5000
    GRAPH_DEFAULT_MAX_DEPTH: int = 2
    GRAPH_MAX_DEPTH_LIMIT: int = 4
    GRAPH_COMMUNITY_ALGORITHM: str = "LOUVAIN"
    GRAPH_COMMUNITY_RANDOM_SEED: int = 42
    GRAPH_VERSION: str = "1.0.0"

    # Phase 14: Timeline Analysis & Anomaly Detection
    TIMELINE_MAX_EVENTS: int = 10000
    ANOMALY_DEFAULT_CONTAMINATION: float = 0.05
    ANOMALY_N_ESTIMATORS: int = 100
    ANOMALY_RANDOM_SEED: int = 42
    ANOMALY_MAX_WINDOW_LIMIT: int = 50000
    ANOMALY_SCORE_THRESHOLD: float = 0.65
    ANOMALY_DEFAULT_WINDOW: str = "15m"
    ANOMALY_VERSION: str = "1.0.0"

    # Phase 15: Intelligent Forensic Report Generation
    REPORT_MAX_TIMELINE_EVENTS: int = 500
    REPORT_MAX_FINDINGS: int = 200
    REPORT_VERSION: str = "1.0.0"
    REPORT_TEMPLATE_VERSION: str = "1.0.0"
    REPORT_STORAGE_DIR: str = "./storage/reports"

    # Database Connection Pool Settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

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


settings = get_settings()
