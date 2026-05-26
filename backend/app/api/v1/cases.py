from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case, CaseAssignment
from app.models.case_timeline_event import CaseTimelineEvent
from app.models.client import Client
from app.models.user import User
from app.schemas.case import AssignedUser, CaseAssignmentRequest, CaseCreate, CaseResponse, CaseUpdate
from app.schemas.timeline import CaseTimelineResponse
from app.services.audit import log_audit_event

router = APIRouter(prefix="/cases", tags=["cases"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]


async def get_case_or_404(db: AsyncSession, case_id: int, organization_id: int) -> Case:
    case = await db.scalar(
        select(Case)
        .where(Case.id == case_id, Case.organization_id == organization_id)
        .options(selectinload(Case.assignments).selectinload(CaseAssignment.user))
    )
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def serialize_case(case: Case) -> CaseResponse:
    assigned_users = [
        AssignedUser(
            id=a.user.id,
            name=a.user.name,
            email=a.user.email,
            role=a.user.role.value,
            status=a.user.status.value,
        )
        for a in case.assignments
    ]
    return CaseResponse(
        id=case.id,
        organization_id=case.organization_id,
        title=case.title,
        description=case.description,
        client_id=case.client_id,
        status=case.status.value,
        priority=case.priority.value,
        created_by=case.created_by,
        assigned_users=assigned_users,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


async def validate_assignments(db: AsyncSession, organization_id: int, user_ids: list[int]) -> list[User]:
    if not user_ids:
        return []
    rows = await db.scalars(
        select(User).where(User.organization_id == organization_id, User.id.in_(user_ids))
    )
    users = rows.all()
    if len(users) != len(set(user_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more assigned users are invalid")
    return users


@router.post("", response_model=CaseResponse)
async def create_case(
    payload: CaseCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await db.scalar(
        select(Client).where(
            Client.id == payload.client_id,
            Client.organization_id == current_user.organization_id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client must belong to your organization")

    users = await validate_assignments(db, current_user.organization_id, payload.assigned_user_ids)
    now = datetime.now(timezone.utc)

    case = Case(
        organization_id=current_user.organization_id,
        title=payload.title,
        description=payload.description,
        client_id=payload.client_id,
        status=payload.status,
        priority=payload.priority,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    await db.flush()

    for user in users:
        db.add(CaseAssignment(case_id=case.id, user_id=user.id))
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="case_created",
        entity_type="case",
        entity_id=str(case.id),
        description=f"Case created: {case.title}",
        metadata_json={"client_id": case.client_id, "status": case.status.value, "priority": case.priority.value},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    await db.commit()
    reloaded = await get_case_or_404(db, case.id, current_user.organization_id)
    return serialize_case(reloaded)


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    rows = await db.scalars(
        select(Case)
        .where(Case.organization_id == current_user.organization_id)
        .options(selectinload(Case.assignments).selectinload(CaseAssignment.user))
        .order_by(Case.created_at.desc())
    )
    return [serialize_case(c) for c in rows.all()]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    return serialize_case(case)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: int,
    payload: CaseUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)

    if payload.client_id is not None:
        client = await db.scalar(
            select(Client).where(
                Client.id == payload.client_id,
                Client.organization_id == current_user.organization_id,
            )
        )
        if not client:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client must belong to your organization")

    updates = payload.model_dump(exclude_unset=True, exclude={"assigned_user_ids"})
    for key, value in updates.items():
        setattr(case, key, value)

    if payload.assigned_user_ids is not None:
        users = await validate_assignments(db, current_user.organization_id, payload.assigned_user_ids)
        existing_by_user = {a.user_id: a for a in case.assignments}
        wanted = set(payload.assigned_user_ids)
        for assignment in list(case.assignments):
            if assignment.user_id not in wanted:
                await db.delete(assignment)
        for user in users:
            if user.id not in existing_by_user:
                db.add(CaseAssignment(case_id=case.id, user_id=user.id))

    case.updated_at = datetime.now(timezone.utc)
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="case_updated",
        entity_type="case",
        entity_id=str(case.id),
        description=f"Case updated: {case.title}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    reloaded = await get_case_or_404(db, case.id, current_user.organization_id)
    return serialize_case(reloaded)


@router.delete("/{case_id}")
async def delete_case(
    case_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="case_deleted",
        entity_type="case",
        entity_id=str(case.id),
        description=f"Case deleted: {case.title}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.delete(case)
    await db.commit()
    return {"ok": True}


@router.post("/{case_id}/assign", response_model=CaseResponse)
async def assign_case_team(
    case_id: int,
    payload: CaseAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    users = await validate_assignments(db, current_user.organization_id, payload.user_ids)

    existing = {a.user_id for a in case.assignments}
    for user in users:
        if user.id not in existing:
            db.add(CaseAssignment(case_id=case.id, user_id=user.id))

    case.updated_at = datetime.now(timezone.utc)
    await db.commit()
    reloaded = await get_case_or_404(db, case.id, current_user.organization_id)
    return serialize_case(reloaded)


@router.get("/{case_id}/team", response_model=list[AssignedUser])
async def get_case_team(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    return [
        AssignedUser(
            id=a.user.id,
            name=a.user.name,
            email=a.user.email,
            role=a.user.role.value,
            status=a.user.status.value,
        )
        for a in case.assignments
    ]


@router.get("/{case_id}/timeline", response_model=list[CaseTimelineResponse])
async def get_case_timeline(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    rows = await db.scalars(
        select(CaseTimelineEvent)
        .where(
            CaseTimelineEvent.case_id == case.id,
            CaseTimelineEvent.organization_id == current_user.organization_id,
        )
        .order_by(CaseTimelineEvent.created_at.desc())
    )
    return [
        CaseTimelineResponse(
            id=e.id,
            organization_id=e.organization_id,
            case_id=e.case_id,
            actor_id=e.actor_id,
            event_type=e.event_type,
            title=e.title,
            description=e.description,
            metadata=e.metadata_json,
            created_at=e.created_at,
        )
        for e in rows.all()
    ]
