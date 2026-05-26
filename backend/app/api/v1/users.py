from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


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
