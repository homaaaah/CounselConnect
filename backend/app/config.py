"""Application settings (single definition, re-exported by app.core.config).

Loaded from COUNSELCONNECT_* environment variables per NAMING_CONVENTIONS.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COUNSELCONNECT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database (MySQL 8.4 LTS via PyMySQL, sync per ADR-002) ---
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "counselconnect"
    db_user: str = ""
    db_password: str = ""

    # --- Application ---
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- Session cookie (ADR-019) ---
    # True behind HTTPS (deployment); False only for localhost dev where
    # browsers refuse Secure cookies on plain http://127.0.0.1 in some cases.
    cookie_secure: bool = False

    # --- Non-MySQL storage roots (never inside version control) ---
    cor_storage_root: str = "./var/cor"
    resource_storage_root: str = "./var/resources"

    # --- COR upload (provisional limit; final policy pending ADR-P05) ---
    cor_max_mb: int = 10

    # --- Email notifications (Gmail SMTP; skipped silently when unset) ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # Gmail App Password (16 chars), NOT the login password

    @property
    def database_url(self) -> str:
        """Sync SQLAlchemy URL for PyMySQL (utf8mb4, UTC connection)."""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
