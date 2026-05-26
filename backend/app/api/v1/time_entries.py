from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry import TimeEntryCreate, TimeEntryResponse, TimeEntryUpdate
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/time-entries", tags=["time-entries"])
ALLOWED = ["partner", "admin", "lawyer", "paralegal"]


def ser(t: TimeEntry) -> TimeEntryResponse:
    return TimeEntryResponse(**{c: getattr(t, c) for c in TimeEntryResponse.model_fields.keys()})


async def validate_case_user(db: AsyncSession, org_id: int, case_id: int, user_id: int):
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == org_id))
    if not case:
        raise HTTPException(status_code=400, detail="Case must belong to your organization")
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == org_id))
    if not user:
        raise HTTPException(status_code=400, detail="User must belong to your organization")
    return case


@router.post("", response_model=TimeEntryResponse)
async def create_time_entry(payload: TimeEntryCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    case = await validate_case_user(db, current_user.organization_id, payload.case_id, payload.user_id)
    now = datetime.now(timezone.utc)
    obj = TimeEntry(organization_id=current_user.organization_id, created_at=now, updated_at=now, billed=False, **payload.model_dump())
    db.add(obj)
    await db.flush()
    await create_case_timeline_event(db, organization_id=current_user.organization_id, case_id=case.id, actor_id=current_user.id, event_type="time_entry_added", title="Time entry added", metadata_json={"time_entry_id": obj.id})
    await db.commit(); await db.refresh(obj)
    return ser(obj)


@router.get("", response_model=list[TimeEntryResponse])
async def list_time_entries(case_id: int | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    q = select(TimeEntry).where(TimeEntry.organization_id == current_user.organization_id)
    if case_id is not None: q = q.where(TimeEntry.case_id == case_id)
    rows = await db.scalars(q.order_by(TimeEntry.entry_date.desc()))
    return [ser(x) for x in rows.all()]


@router.get("/{entry_id}", response_model=TimeEntryResponse)
async def get_time_entry(entry_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    obj = await db.scalar(select(TimeEntry).where(TimeEntry.id == entry_id, TimeEntry.organization_id == current_user.organization_id))
    if not obj: raise HTTPException(status_code=404, detail="Time entry not found")
    return ser(obj)


@router.patch("/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(entry_id: int, payload: TimeEntryUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    obj = await db.scalar(select(TimeEntry).where(TimeEntry.id == entry_id, TimeEntry.organization_id == current_user.organization_id))
    if not obj: raise HTTPException(status_code=404, detail="Time entry not found")
    updates = payload.model_dump(exclude_unset=True)
    cid = updates.get("case_id", obj.case_id); uid = updates.get("user_id", obj.user_id)
    await validate_case_user(db, current_user.organization_id, cid, uid)
    for k, v in updates.items(): setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    await db.commit(); await db.refresh(obj)
    return ser(obj)


@router.delete("/{entry_id}")
async def delete_time_entry(entry_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    obj = await db.scalar(select(TimeEntry).where(TimeEntry.id == entry_id, TimeEntry.organization_id == current_user.organization_id))
    if not obj: raise HTTPException(status_code=404, detail="Time entry not found")
    await db.delete(obj); await db.commit(); return {"ok": True}
