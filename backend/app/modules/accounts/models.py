"""accounts ORM models: campuses, departments, programs, users, student_profiles.

Column/constraint names mirror CounselConnect_Initial_Database_v4.sql exactly.
Roles are fixed: STUDENT, GUIDANCE_STAFF, COUNSELOR (no ADMIN role exists).
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class Campus(Base):
    __tablename__ = "campuses"
    __table_args__ = (UniqueConstraint("campus_name", name="uq_campuses_name"),)

    campus_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    campus_name: Mapped[str] = mapped_column(String(150), nullable=False)
    guidance_office_location: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"), insert_default=True)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("department_name", name="uq_departments_name"),)

    department_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    department_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"), insert_default=True)


class Program(Base):
    __tablename__ = "programs"
    __table_args__ = (
        UniqueConstraint("program_code", name="uq_programs_code"),
        Index("idx_programs_department", "department_id"),
    )

    program_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("departments.department_id", name="fk_programs_department", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    program_code: Mapped[str] = mapped_column(String(50), nullable=False)
    program_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"), insert_default=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("idx_users_role_status", "role_code", "account_status"),
        CheckConstraint(
            "role_code IN ('STUDENT', 'GUIDANCE_STAFF', 'COUNSELOR')",
            name="chk_users_role",
        ),
        CheckConstraint(
            "account_status IN ('PENDING_VERIFICATION', 'ACTIVE', 'VERIFICATION_EXPIRED')",
            name="chk_users_account_status",
        ),
    )

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False)
    account_status: Mapped[str] = mapped_column(String(40), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    updated_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow, onupdate=utcnow)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        UniqueConstraint("student_number", name="uq_student_profiles_number"),
        Index("idx_student_profiles_campus", "campus_id"),
        Index("idx_student_profiles_program", "program_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_student_profiles_user", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    student_number: Mapped[str] = mapped_column(String(50), nullable=False)
    campus_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("campuses.campus_id", name="fk_student_profiles_campus", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    program_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("programs.program_id", name="fk_student_profiles_program", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    year_level: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
