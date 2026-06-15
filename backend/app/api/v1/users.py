from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, role_guard
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]


@router.get("", response_model=list[UserOut])
async def list_users(
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    query = select(User).where(User.organization_id == current_user.organization_id).order_by(User.name.asc(), User.email.asc())
    if search and search.strip():
        needle = f"%{search.strip()}%"
        query = query.where(or_(User.name.ilike(needle), User.email.ilike(needle)))

    users = (await db.scalars(query)).all()
    return [
        UserOut(
            id=user.id,
            organization_id=user.organization_id,
            name=user.name,
            email=user.email,
            role=user.role.value,
            status=user.status.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        for user in users
    ]


@router.get("/me", response_model=UserOut)
async def user_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        organization_id=current_user.organization_id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role.value,
        status=current_user.status.value,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )
