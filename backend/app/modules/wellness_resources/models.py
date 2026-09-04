"""wellness_resources ORM models.

Mirrors CounselConnect_Initial_Database_v4.sql exactly: bounded-metadata
discovery pipeline (PENDING -> PUBLISHED/REJECTED/DISABLED), content-shape
and provenance CHECKs, categories join table, controlled attachments.
Full third-party article bodies are NEVER mirrored.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class ResourceSource(Base):
    __tablename__ = "resource_sources"
    __table_args__ = (
        UniqueConstraint("canonical_domain", name="uq_resource_sources_domain"),
        CheckConstraint(
            "acquisition_mode IN ('RSS', 'ATOM', 'STRUCTURED', 'SCRAPING_FALLBACK')",
            name="chk_resource_sources_acquisition_mode",
        ),
    )

    source_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    canonical_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    feed_url: Mapped[str | None] = mapped_column(String(2048))
    acquisition_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("TRUE"), insert_default=True)
    created_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    updated_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow, onupdate=utcnow)


class ResourceCategory(Base):
    __tablename__ = "resource_categories"
    __table_args__ = (
        UniqueConstraint("category_name", name="uq_resource_categories_name"),
        UniqueConstraint("slug", name="uq_resource_categories_slug"),
    )

    category_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    category_name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("TRUE"), insert_default=True)


class WellnessResource(Base):
    __tablename__ = "wellness_resources"
    __table_args__ = (
        Index("idx_wellness_resources_source", "source_id", "status", "discovered_at"),
        Index("idx_wellness_resources_status", "status", "published_at"),
        Index("idx_wellness_resources_creator", "created_by_user_id"),
        Index("idx_wellness_resources_reviewer", "reviewed_by_user_id"),
        CheckConstraint(
            "resource_type IN ('EXTERNAL_LINK', 'INTERNAL_ARTICLE', 'INTERNAL_FILE')",
            name="chk_wellness_resources_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'REJECTED', 'DISABLED')",
            name="chk_wellness_resources_status",
        ),
        CheckConstraint(
            "(resource_type = 'EXTERNAL_LINK' AND external_url IS NOT NULL AND content_body IS NULL) "
            "OR (resource_type = 'INTERNAL_ARTICLE' AND external_url IS NULL AND content_body IS NOT NULL) "
            "OR (resource_type = 'INTERNAL_FILE' AND external_url IS NULL AND content_body IS NULL)",
            name="chk_wellness_resources_content_shape",
        ),
        # v4.1: chk_wellness_resources_provenance and
        # chk_wellness_resources_review_state are enforced in the service
        # layer, not DDL (MySQL 8 forbids CHECKs referencing FK-action columns).
    )

    resource_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("resource_sources.source_id", name="fk_wellness_resources_source", ondelete="SET NULL", onupdate="CASCADE"),
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_wellness_resources_creator", ondelete="SET NULL", onupdate="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(String(2048))
    content_body: Mapped[str | None] = mapped_column(LONGTEXT)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PENDING")
    discovered_at: Mapped[object | None] = mapped_column(DATETIME6)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_wellness_resources_reviewer", ondelete="SET NULL", onupdate="CASCADE"),
    )
    reviewed_at: Mapped[object | None] = mapped_column(DATETIME6)
    published_at: Mapped[object | None] = mapped_column(DATETIME6)
    created_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    updated_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow, onupdate=utcnow)


class ResourceFile(Base):
    __tablename__ = "resource_files"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_resource_files_storage_key"),
        Index("idx_resource_files_resource", "resource_id", "display_order"),
        CheckConstraint("size_bytes > 0", name="chk_resource_files_size"),
    )

    resource_file_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("wellness_resources.resource_id", name="fk_resource_files_resource", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    display_order: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    uploaded_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)


class WellnessResourceCategory(Base):
    __tablename__ = "wellness_resource_categories"
    __table_args__ = (Index("idx_resource_category_category", "category_id"),)

    resource_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("wellness_resources.resource_id", name="fk_resource_category_resource", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("resource_categories.category_id", name="fk_resource_category_category", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
