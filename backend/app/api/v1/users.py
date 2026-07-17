from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, role_guard
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UserOut, UserProfileUpdate
from app.services.profile_images import delete_profile_image, resolve_profile_image_path, store_profile_image

router = APIRouter(prefix="/users", tags=["users"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]
MIN_PASSWORD_LENGTH = 8


async def user_out(db: AsyncSession, user: User) -> UserOut:
    org_name = await db.scalar(select(Organization.name).where(Organization.id == user.organization_id))
    return UserOut(
        id=user.id,
        organization_id=user.organization_id,
        name=user.name,
        email=user.email,
        role=user.role.value,
        status=user.status.value,
        organization_name=org_name,
        profile_image_updated_at=getattr(user, "profile_image_updated_at", None),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


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
    return [await user_out(db, user) for user in users]


@router.get("/me", response_model=UserOut)
async def user_me(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await user_out(db, current_user)


@router.patch("/me", response_model=UserOut)
async def update_user_me(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full name is required")
    current_user.name = name
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return await user_out(db, current_user)


@router.post("/me/password")
async def change_my_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New passwords do not match")
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/me/profile-picture", response_model=UserOut)
async def upload_my_profile_picture(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    previous_path = getattr(current_user, "profile_image_path", None)
    relative_path, _file_path = await store_profile_image(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        upload=file,
    )
    current_user.profile_image_path = relative_path
    current_user.profile_image_updated_at = datetime.now(timezone.utc)
    current_user.updated_at = current_user.profile_image_updated_at
    await db.commit()
    await db.refresh(current_user)
    delete_profile_image(previous_path)
    return await user_out(db, current_user)


@router.delete("/me/profile-picture", response_model=UserOut)
async def remove_my_profile_picture(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    previous_path = getattr(current_user, "profile_image_path", None)
    current_user.profile_image_path = None
    current_user.profile_image_updated_at = datetime.now(timezone.utc)
    current_user.updated_at = current_user.profile_image_updated_at
    await db.commit()
    await db.refresh(current_user)
    delete_profile_image(previous_path)
    return await user_out(db, current_user)


@router.get("/me/profile-picture")
async def get_my_profile_picture(current_user: User = Depends(get_current_user)):
    file_path = resolve_profile_image_path(getattr(current_user, "profile_image_path", None))
    if not file_path or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile picture not found")
    suffix = file_path.suffix.lower()
    media_type = "image/jpeg"
    if suffix == ".png":
        media_type = "image/png"
    elif suffix == ".webp":
        media_type = "image/webp"
    return FileResponse(file_path, media_type=media_type)
