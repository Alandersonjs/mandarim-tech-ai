"""Centralised application settings, read from environment variables."""

import os
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache


def _parse_csv(value: str) -> list[str]:
    """Convert a comma-separated string into a clean list of values."""
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Immutable settings container.

    Environment variables:
        DATABASE_URL: SQLAlchemy URL (default: local SQLite file).
                      Example for PostgreSQL:
                      postgresql+psycopg2://user:password@localhost:5432/mandarim_tech
        CORS_ORIGINS: Comma-separated list of allowed front-end origins.
        TTS_CACHE_DIR: Folder where synthesized MP3 files are cached.
        TTS_TIMEOUT_SECONDS: Maximum time to wait for the TTS provider.
    """

    app_name: str = "Mandarim Tech AI"
    app_version: str = "0.3.0"
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./mandarim_tech.db")
    )
    tts_cache_dir: str = field(
        default_factory=lambda: os.getenv(
            "TTS_CACHE_DIR", os.path.join(tempfile.gettempdir(), "mandarim_tts_cache")
        )
    )
    tts_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("TTS_TIMEOUT_SECONDS", "20"))
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _parse_csv(
            os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
        )
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (built only once per process)."""
    return Settings()
