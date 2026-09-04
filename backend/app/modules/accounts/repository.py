"""accounts repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.accounts.models import Campus, Department, Program, StudentProfile, User


class AccountsRepository(BaseRepository[User]):
    """Owns all accounts-domain SQLAlchemy queries."""

    model = User

    # -- reference data (public) ---------------------------------------

    def find_campus(self, campus_id: int) -> Campus | None:
        return self.session.get(Campus, campus_id)

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

    def find_student_profile(self, user_id: int) -> StudentProfile | None:
        return self.session.get(StudentProfile, user_id)

    def find_student_profile_by_number(self, student_number: str) -> StudentProfile | None:
        return self.session.scalar(
            select(StudentProfile).where(StudentProfile.student_number == student_number)
        )
