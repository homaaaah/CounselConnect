"""accounts repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import func, or_, select

from app.modules.bases import BaseRepository
from app.modules.accounts.models import Campus, Department, Program, StudentProfile, User


class AccountsRepository(BaseRepository[User]):
    """Owns all accounts-domain SQLAlchemy queries."""

    model = User

    # -- reference data (public) ---------------------------------------

    def find_campus(self, campus_id: int) -> Campus | None:
        return self.session.get(Campus, campus_id)

    def lock_campus(self, campus_id: int) -> Campus | None:
        return self.session.scalar(select(Campus).where(Campus.campus_id == campus_id)
            .with_for_update().execution_options(populate_existing=True))

    def find_department(self, department_id: int) -> Department | None:
        return self.session.get(Department, department_id)

    def find_program(self, program_id: int) -> Program | None:
        return self.session.get(Program, program_id)

    def list_active_campuses(self) -> list[Campus]:
        return list(self.session.scalars(select(Campus).where(Campus.is_active.is_(True))))

    def list_active_programs(self) -> list[Program]:
        return list(self.session.scalars(select(Program).where(Program.is_active.is_(True))))

    # -- users ----------------------------------------------------------

    def find_user_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def list_active_guidance_staff(self) -> list[User]:
        return list(self.session.scalars(
            select(User)
            .where(User.role_code == "GUIDANCE_STAFF", User.account_status == "ACTIVE")
            .order_by(User.last_name, User.first_name, User.user_id)
        ))

    def lock_user(self, user_id: int) -> User | None:
        """Serialize verification submissions/decisions for one student."""
        return self.session.scalar(
            select(User).where(User.user_id == user_id).with_for_update()
            .execution_options(populate_existing=True)
        )

    def find_student_profile(self, user_id: int) -> StudentProfile | None:
        return self.session.get(StudentProfile, user_id)

    def find_student_profile_by_number(self, student_number: str) -> StudentProfile | None:
        return self.session.scalar(
            select(StudentProfile).where(StudentProfile.student_number == student_number)
        )

    # -- counselor directory --------------------------------------------

    def list_students(
        self, *, q: str | None = None, account_status: str | None = None
    ) -> list[tuple[User, StudentProfile | None]]:
        """All STUDENT users (with profile when confirmed), optional filters.

        Read-only Counselor directory. `q` matches email, name, or student
        number (case-insensitive substring). Ordered by name for stable output.
        """
        stmt = (
            select(User, StudentProfile)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.user_id)
            .where(User.role_code == "STUDENT")
        )
        if account_status:
            stmt = stmt.where(User.account_status == account_status)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.email).like(like),
                    func.lower(User.first_name).like(like),
                    func.lower(User.last_name).like(like),
                    func.lower(func.coalesce(StudentProfile.student_number, "")).like(like),
                )
            )
        stmt = stmt.order_by(User.last_name, User.first_name, User.user_id)
        return [(user, profile) for user, profile in self.session.execute(stmt).all()]
