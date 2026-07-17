from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.enums import RecordStatus, UserRole
from app.models.user import User
from app.models.user_invite import UserInvite
from app.core.security import hash_password
from app.schemas.admin import AdminUserCreate, AdminUserUpdate, InviteCreate, InviteResponse
from app.schemas.user import UserOut
from app.services.audit import log_audit_event
from app.services.email import build_invite_email
from app.services.jobs import enqueue_email

router = APIRouter(prefix="/admin", tags=["admin"])
ALLOWED_ADMIN = ["partner", "admin"]
VALID_INVITE_ROLES = {"partner", "admin", "lawyer", "paralegal"}
VALID_USER_ROLES = {"partner", "admin", "lawyer", "paralegal", "client"}
VALID_STATUSES = {"active", "inactive"}
MIN_PASSWORD_LENGTH = 8


def invite_out(inv: UserInvite) -> InviteResponse:
    return InviteResponse(
        id=inv.id,
        organization_id=inv.organization_id,
        email=inv.email,
        role=inv.role,
        token=inv.token,
        status=inv.status,
        expires_at=inv.expires_at,
        invited_by=inv.invited_by,
        created_at=inv.created_at,
    )


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        organization_id=user.organization_id,
        name=user.name,
        email=user.email,
        role=user.role.value,
        status=user.status.value,
        profile_image_updated_at=getattr(user, "profile_image_updated_at", None),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def count_active_role(db: AsyncSession, org_id: int, role: UserRole) -> int:
    return int((await db.scalar(select(func.count(User.id)).where(User.organization_id == org_id, User.role == role, User.status == RecordStatus.active))) or 0)


@router.post("/invites", response_model=InviteResponse)
async def create_invite(payload: InviteCreate, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_ADMIN))):
    raise HTTPException(status_code=410, detail="Invitations are disabled. Create the team member directly.")
    role = payload.role.lower()
    if role not in VALID_INVITE_ROLES:
        raise HTTPException(status_code=400, detail="Invalid invite role")

    existing_user = await db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already belongs to a user")

    now = datetime.now(timezone.utc)
    invite = UserInvite(
        organization_id=current_user.organization_id,
        email=payload.email,
        role=role,
        token=secrets.token_urlsafe(32),
        status="pending",
        expires_at=now + timedelta(hours=48),
        invited_by=current_user.id,
        created_at=now,
    )
    db.add(invite)
    await db.flush()
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="invite_created",
        entity_type="user_invite",
        entity_id=str(invite.id),
        description=f"Invite created for {invite.email}",
        metadata_json={"email": invite.email, "role": invite.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(invite)
    subject, html_body, text_body = build_invite_email(role=invite.role, token=invite.token)
    enqueue_email(
        background_tasks,
        to_email=invite.email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
    return invite_out(invite)


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_ADMIN))):
    rows = (await db.scalars(select(UserInvite).where(UserInvite.organization_id == current_user.organization_id).order_by(UserInvite.created_at.desc()))).all()
    return [invite_out(i) for i in rows]


@router.post("/invites/{invite_id}/resend", response_model=InviteResponse)
async def resend_invite(invite_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_ADMIN))):
    raise HTTPException(status_code=410, detail="Invitation resend is disabled. Create the team member directly if needed.")
    invite = await db.scalar(select(UserInvite).where(UserInvite.id == invite_id, UserInvite.organization_id == current_user.organization_id))
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.now(timezone.utc)
    invite.token = secrets.token_urlsafe(32)
    invite.status = "pending"
    invite.expires_at = now + timedelta(hours=48)
    await db.commit()
    await db.refresh(invite)
    return invite_out(invite)


@router.post("/invites/{invite_id}/cancel", response_model=InviteResponse)
async def cancel_invite(invite_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_ADMIN))):
    invite = await db.scalar(select(UserInvite).where(UserInvite.id == invite_id, UserInvite.organization_id == current_user.organization_id))
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.status = "expired"
    invite.expires_at = datetime.now(timezone.utc)
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="invite_cancelled",
        entity_type="user_invite",
        entity_id=str(invite.id),
        description=f"Invite cancelled for {invite.email}",
        metadata_json={"email": invite.email, "role": invite.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(invite)
    return invite_out(invite)


@router.get("/users", response_model=list[UserOut])
async def list_admin_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_ADMIN))):
    rows = (await db.scalars(select(User).where(User.organization_id == current_user.organization_id).order_by(User.created_at.asc()))).all()
    return [user_out(u) for u in rows]


@router.post("/users", response_model=UserOut)
async def create_admin_user(
    payload: AdminUserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_ADMIN)),
):
    role = payload.role.lower()
    if role not in VALID_INVITE_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    status_value = payload.status.lower()
    if status_value not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Full name is required")

    email = str(payload.email).strip().lower()
    existing_user = await db.scalar(select(User).where(User.email == email))
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already belongs to a user")

    now = datetime.now(timezone.utc)
    user = User(
        organization_id=current_user.organization_id,
        name=name,
        email=email,
        hashed_password=hash_password(payload.password),
        role=UserRole(role),
        status=RecordStatus(status_value),
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="team_member_created",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Team member created: {user.email}",
        metadata_json={"created_user_id": user.id, "role": user.role.value},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(user)
    return user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_admin_user(user_id: int, payload: AdminUserUpdate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_ADMIN))):
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == current_user.organization_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id and payload.status and payload.status.lower() == "inactive":
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")

    previous_role = user.role.value
    previous_status = user.status.value
    if payload.role is not None:
        next_role = payload.role.lower()
        if next_role not in VALID_USER_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        if user.role == UserRole.partner and next_role != "partner":
            if await count_active_role(db, current_user.organization_id, UserRole.partner) <= 1:
                raise HTTPException(status_code=400, detail="Cannot downgrade last active partner")
        if user.role == UserRole.admin and next_role != "admin":
            if await count_active_role(db, current_user.organization_id, UserRole.admin) <= 1:
                raise HTTPException(status_code=400, detail="Cannot downgrade last active admin")
        user.role = UserRole(next_role)

    if payload.status is not None:
        next_status = payload.status.lower()
        if next_status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        if user.role == UserRole.partner and user.status == RecordStatus.active and next_status == "inactive":
            if await count_active_role(db, current_user.organization_id, UserRole.partner) <= 1:
                raise HTTPException(status_code=400, detail="Cannot deactivate last active partner")
        if user.role == UserRole.admin and user.status == RecordStatus.active and next_status == "inactive":
            if await count_active_role(db, current_user.organization_id, UserRole.admin) <= 1:
                raise HTTPException(status_code=400, detail="Cannot deactivate last active admin")
        user.status = RecordStatus(next_status)

    user.updated_at = datetime.now(timezone.utc)
    if user.role.value != previous_role or user.status.value != previous_status:
        await log_audit_event(
            db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="user_role_status_changed",
            entity_type="user",
            entity_id=str(user.id),
            description=f"Updated user {user.email}",
            metadata_json={
                "before_role": previous_role,
                "after_role": user.role.value,
                "before_status": previous_status,
                "after_status": user.status.value,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    await db.commit()
    await db.refresh(user)
    return user_out(user)


@router.delete("/users/{user_id}")
async def deactivate_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_ADMIN))):
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == current_user.organization_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")

    if user.role == UserRole.partner and user.status == RecordStatus.active:
        if await count_active_role(db, current_user.organization_id, UserRole.partner) <= 1:
            raise HTTPException(status_code=400, detail="Cannot deactivate last active partner")
    if user.role == UserRole.admin and user.status == RecordStatus.active:
        if await count_active_role(db, current_user.organization_id, UserRole.admin) <= 1:
            raise HTTPException(status_code=400, detail="Cannot deactivate last active admin")

    user.status = RecordStatus.inactive
    user.updated_at = datetime.now(timezone.utc)
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="user_role_status_changed",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Deactivated user {user.email}",
        metadata_json={"after_status": "inactive"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return {"ok": True}
