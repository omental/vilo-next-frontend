from sqlalchemy import Select, or_, select

from app.models.case import Case, CaseAssignment
from app.models.user import User


PRIVILEGED_CASE_ROLES = {"partner", "admin", "lawyer"}


def accessible_case_condition(current_user: User):
    """Return the record-level case visibility condition for a staff user."""
    if current_user.role.value in PRIVILEGED_CASE_ROLES:
        return Case.organization_id == current_user.organization_id
    assigned_case_ids = select(CaseAssignment.case_id).where(CaseAssignment.user_id == current_user.id)
    return or_(Case.created_by == current_user.id, Case.id.in_(assigned_case_ids))


def scope_cases(query: Select, current_user: User) -> Select:
    return query.where(
        Case.organization_id == current_user.organization_id,
        accessible_case_condition(current_user),
    )
