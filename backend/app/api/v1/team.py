from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(tags=["team"])


@router.get("/team", response_model=list[UserOut])
async def get_team(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(User).where(User.organization_id == current_user.organization_id).order_by(User.created_at))
    users = result.all()
    return [
        UserOut(
            id=u.id,
            organization_id=u.organization_id,
            name=u.name,
            email=u.email,
            role=u.role.value,
            status=u.status.value,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]
