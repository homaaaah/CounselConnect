"""Application settings (single definition, re-exported by app.core.config).

Loaded from COUNSELCONNECT_* environment variables per NAMING_CONVENTIONS.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class CallIceServerConfig(BaseModel):
    """One ICE server entry, supplied through the environment as JSON."""

    urls: list[str]
    username: str | None = None
    credential: str | None = None


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

    # --- Appointment video calls (ADR-034) ---
    # JSON list, e.g. [{"urls":["stun:host:3478"]},{"urls":["turn:host:3478"],
    # "username":"...","credential":"..."}]. Credentials are only returned to
    # an authorized participant inside the appointment call window.
    call_ice_servers: list[CallIceServerConfig] = [
        CallIceServerConfig(urls=["stun:stun.l.google.com:19302"])
    ]
    call_signal_max_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    call_signal_messages_per_minute: int = Field(default=300, ge=10, le=6_000)

    # --- Non-MySQL storage roots (never inside version control) ---
    cor_storage_root: str = "./var/cor"
    resource_storage_root: str = "./var/resources"

    # --- COR upload (PDF-only limit; policy ratified by ADR-024) ---
    cor_max_mb: int = 10

    # --- Appointment-scoped session documents (private clinical files) ---
    session_document_storage_root: str = "./var/session-documents"
    session_document_max_mb: int = Field(default=10, ge=1, le=50)

    # --- Automated COR screening (ADR-029) ---
    # When disabled the registration-with-COR endpoint fails closed with
    # REGISTRATION_DISABLED; it never auto-activates an account.
    cor_screening_enabled: bool = True
    cor_format_pass_score: float = Field(default=0.60, ge=0.0, le=1.0)
    cor_extraction_pass_score: float = Field(default=0.60, ge=0.0, le=1.0)
    cor_template_version: str = "ucc-registration-v1"
    # External document-processing binaries. Override with absolute paths
    # on deployments where they are not on PATH. Missing binaries make
    # screening fail closed (never auto-activate).
    pdftotext_path: str = "pdftotext"
    pdftoppm_path: str = "pdftoppm"
    tesseract_path: str = "tesseract"

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
