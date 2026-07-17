from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.enums import RecordStatus, UserRole
from app.models.organization import Organization
from app.models.user import User
from app.models.user_invite import UserInvite
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.admin import AcceptInviteRequest
from app.schemas.user import UserOut
from app.services.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing_org = await db.scalar(select(Organization).where(Organization.slug == payload.organization_slug))
    if existing_org:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization slug already exists")

    existing_user = await db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    now = datetime.now(timezone.utc)
    org = Organization(
        name=payload.organization_name,
        slug=payload.organization_slug,
        status=RecordStatus.active,
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.partner,
        status=RecordStatus.active,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    await log_audit_event(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=str(user.id),
        description="User logged in",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def me(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    org_name = await db.scalar(select(Organization.name).where(Organization.id == current_user.organization_id))
    return UserOut(
        id=current_user.id,
        organization_id=current_user.organization_id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role.value,
        status=current_user.status.value,
        organization_name=org_name,
        profile_image_updated_at=getattr(current_user, "profile_image_updated_at", None),
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.post("/accept-invite", response_model=TokenResponse)
async def accept_invite(payload: AcceptInviteRequest, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    invite = await db.scalar(select(UserInvite).where(UserInvite.token == payload.token))
    if not invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite token")
    now = datetime.now(timezone.utc)
    if invite.status != "pending" or invite.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite is expired or already used")

    existing_user = await db.scalar(select(User).where(User.email == invite.email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    user = User(
        organization_id=invite.organization_id,
        name=payload.name,
        email=invite.email,
        hashed_password=hash_password(payload.password),
        role=UserRole(invite.role),
        status=RecordStatus.active,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    invite.status = "accepted"
    await db.flush()
    await log_audit_event(
        db,
        organization_id=invite.organization_id,
        user_id=user.id,
        action="invite_accepted",
        entity_type="user_invite",
        entity_id=str(invite.id),
        description="Invite accepted and account created",
        metadata_json={"email": invite.email, "role": invite.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))
