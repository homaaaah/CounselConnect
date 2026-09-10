"""appointments ORM models: availability_slots, appointments.

Mirrors CounselConnect_Initial_Database_v4.sql exactly, including the
active_reservation_slot_id STORED generated column (double-booking guard)
and the location-snapshot CHECK (ONLINE -> NULL, FACE_TO_FACE -> required).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (
        UniqueConstraint("counselor_user_id", "campus_id", "starts_at", "ends_at", name="uq_availability_slot"),
        Index("idx_availability_search", "campus_id", "delivery_mode", "status", "starts_at"),
        Index("idx_availability_counselor", "counselor_user_id", "starts_at"),
        CheckConstraint("ends_at > starts_at", name="chk_availability_time"),
        CheckConstraint("status IN ('AVAILABLE', 'RESERVED')", name="chk_availability_status"),
        CheckConstraint(
            "delivery_mode IN ('ONLINE', 'FACE_TO_FACE', 'BOTH')",
            name="chk_availability_delivery_mode",
        ),
    )

    slot_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    counselor_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_availability_counselor", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    campus_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("campuses.campus_id", name="fk_availability_campus", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    delivery_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_at: Mapped[object] = mapped_column(DATETIME6, nullable=False)
    ends_at: Mapped[object] = mapped_column(DATETIME6, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="AVAILABLE")
    created_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("idx_appointments_student", "student_user_id", "status", "created_at"),
        Index("idx_appointments_counselor", "counselor_user_id", "status", "created_at"),
        Index("idx_appointments_slot_status", "availability_slot_id", "status"),
        Index("idx_appointments_online_session", "appointment_mode", "status", "conversation_id"),
        UniqueConstraint("active_reservation_slot_id", name="uq_appointments_active_slot"),
        UniqueConstraint("conversation_id", name="uq_appointments_conversation"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'REJECTED', 'NO_SHOW')",
            name="chk_appointments_status",
        ),
        CheckConstraint(
            "appointment_mode IN ('ONLINE', 'FACE_TO_FACE')",
            name="chk_appointments_mode",
        ),
        CheckConstraint(
            "(appointment_mode = 'ONLINE' AND meeting_location IS NULL) OR "
            "(appointment_mode = 'FACE_TO_FACE' AND meeting_location IS NOT NULL)",
            name="chk_appointments_location_shape",
        ),
    )

    appointment_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    student_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_appointments_student", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    counselor_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_appointments_counselor", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    availability_slot_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("availability_slots.slot_id", name="fk_appointments_slot", ondelete="RESTRICT", onupdate="RESTRICT"),  # v4.1: base column of STORED generated column
        nullable=False,
    )
    appointment_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    meeting_location: Mapped[str | None] = mapped_column(String(255))
    conversation_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("conversations.conversation_id", name="fk_appointments_conversation", ondelete="SET NULL", onupdate="CASCADE"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PENDING")
    active_reservation_slot_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        Computed(
            "CASE WHEN status IN ('PENDING', 'CONFIRMED') THEN availability_slot_id ELSE NULL END",
            persisted=True,
        ),
    )
    rejection_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    updated_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow, onupdate=utcnow)
