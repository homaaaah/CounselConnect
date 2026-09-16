"""Application settings (single definition, re-exported by app.core.config).

Loaded from COUNSELCONNECT_* environment variables per NAMING_CONVENTIONS.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


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

    # --- Scheduled appointment chat (ADR-028) ---
    chat_grace_minutes: int = Field(default=15, ge=0, le=120)
    chat_retention_days: int = Field(default=30, ge=1, le=365)
    chat_max_message_characters: int = Field(default=4000, ge=1, le=20_000)
    chat_maintenance_interval_seconds: int = Field(default=30, ge=1, le=3600)

    # --- Non-MySQL storage roots (never inside version control) ---
    cor_storage_root: str = "./var/cor"
    resource_storage_root: str = "./var/resources"

    # --- COR upload (PDF-only limit; policy ratified by ADR-024) ---
    cor_max_mb: int = 10

    # --- Email notifications (Gmail SMTP; skipped silently when unset) ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # Gmail App Password (16 chars), NOT the login password

    @property
    def database_url(self) -> str:
        """Sync SQLAlchemy URL for PyMySQL (utf8mb4, UTC connection)."""
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
