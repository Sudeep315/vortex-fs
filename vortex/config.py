import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App General
    PROJECT_NAME: str = "VortexFS"
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEBUG: bool = True
    DATA_DIR: Path = Path("data")

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Storage Backend
    # Online store: 'memory' (ultra-fast zero-dep) or 'redis' (production distributed)
    ONLINE_STORE_TYPE: Literal["memory", "redis"] = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Offline store: 'duckdb' (high-performance embedded OLAP) or 'clickhouse' (scale-out OLAP)
    OFFLINE_STORE_TYPE: Literal["duckdb", "clickhouse"] = "duckdb"
    DUCKDB_PATH: Path = Path("data/vortex_offline.duckdb")
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 9000
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = ""
    CLICKHOUSE_DB: str = "vortex"

    # Ingestion Buffer & Stream Settings
    STREAM_BACKEND: Literal["memory", "redis", "kafka"] = "memory"
    INGESTION_BATCH_SIZE: int = 500
    INGESTION_FLUSH_INTERVAL_SEC: float = 1.0

    # Feature Store Defaults
    DEFAULT_ONLINE_TTL_SECONDS: int = 86400 * 30  # 30 days

    model_config = SettingsConfigDict(
        env_prefix="VORTEX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def init_directories(self) -> None:
        """Ensure necessary local data directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if self.DUCKDB_PATH.parent:
            self.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.init_directories()
