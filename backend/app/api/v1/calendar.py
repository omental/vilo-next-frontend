from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.calendar_event import CalendarEvent
from app.models.case import Case
from app.models.task import Task
from app.models.user import User
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventResponse, CalendarEventUpdate
from app.api.v1.tasks import is_task_overdue, normalize_priority, normalize_status
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/calendar/events", tags=["calendar"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]
VALID_EVENT_TYPES = {
    "meeting", "hearing", "deadline", "todo", "consultation",
    "court", "client", "travel", "staff", "note",
}


def serialize(event: CalendarEvent) -> CalendarEventResponse:
    return CalendarEventResponse(
        id=event.id,
        organization_id=event.organization_id,
        case_id=event.case_id,
        client_id=None,
        created_by=event.created_by,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        start_at=event.start_at,
        end_at=event.end_at,
        reminder_at=getattr(event, "reminder_at", None),
        location=event.location,
        source_type="calendar_event",
        source_id=event.id,
        task_id=None,
        status=None,
        priority=None,
        completed=None,
        is_overdue=None,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def serialize_task_as_event(task: Task) -> CalendarEventResponse:
    return CalendarEventResponse(
        id=task.id,
        organization_id=task.organization_id,
        case_id=task.case_id,
        client_id=task.client_id,
        created_by=task.created_by,
        title=task.title,
        description=task.description,
        event_type="task",
        start_at=task.due_date,
        end_at=None,
        reminder_at=task.reminder_at,
        location=None,
        source_type="task",
        source_id=task.id,
        task_id=task.id,
        status=normalize_status(task.status),
        priority=normalize_priority(task.priority),
        completed=normalize_status(task.status) == "completed",
        is_overdue=is_task_overdue(task),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


async def validate_case(db: AsyncSession, organization_id: int, case_id: int | None) -> None:
    if case_id is None:
        return
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == organization_id))
    if not case:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case must belong to your organization")


def validate_type(event_type: str | None) -> None:
    if event_type is not None and event_type not in VALID_EVENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event type")


@router.post("", response_model=CalendarEventResponse)
async def create_event(
    payload: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    validate_type(payload.event_type)
    await validate_case(db, current_user.organization_id, payload.case_id)

    now = datetime.now(timezone.utc)
    event = CalendarEvent(
        organization_id=current_user.organization_id,
        case_id=payload.case_id,
        created_by=current_user.id,
        title=payload.title,
        description=payload.description,
        event_type=payload.event_type,
        start_at=payload.start_at,
        end_at=payload.end_at,
        reminder_at=payload.reminder_at,
        location=payload.location,
        created_at=now,
        updated_at=now,
    )
    db.add(event)
    await db.flush()

    if event.case_id:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=event.case_id,
            actor_id=current_user.id,
            event_type="event_scheduled",
            title=f"Event scheduled: {event.title}",
            metadata_json={"calendar_event_id": event.id, "event_type": event.event_type},
        )

    await db.commit()
    await db.refresh(event)
    return serialize(event)


@router.get("", response_model=list[CalendarEventResponse])
async def list_events(
    case_id: int | None = Query(default=None),
    include_tasks: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    query = select(CalendarEvent).where(CalendarEvent.organization_id == current_user.organization_id)
    if case_id is not None:
        query = query.where(CalendarEvent.case_id == case_id)
    rows = await db.scalars(query.order_by(CalendarEvent.start_at.asc()))
    items = [serialize(event) for event in rows.all()]

    if include_tasks:
        task_query = select(Task).where(
            Task.organization_id == current_user.organization_id,
            Task.due_date.is_not(None),
            Task.archived_at.is_(None),
        )
        if case_id is not None:
            task_query = task_query.where(Task.case_id == case_id)
        task_rows = await db.scalars(task_query.order_by(Task.due_date.asc()))
        items.extend(serialize_task_as_event(task) for task in task_rows.all())
        items.sort(key=lambda item: item.start_at)

    return items


@router.get("/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    event = await db.scalar(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.organization_id == current_user.organization_id)
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return serialize(event)


@router.patch("/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: int,
    payload: CalendarEventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    event = await db.scalar(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.organization_id == current_user.organization_id)
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    updates = payload.model_dump(exclude_unset=True)
    validate_type(updates.get("event_type"))
    if "case_id" in updates:
        await validate_case(db, current_user.organization_id, updates["case_id"])

    for key, value in updates.items():
        setattr(event, key, value)
    event.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(event)
    return serialize(event)


@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    event = await db.scalar(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.organization_id == current_user.organization_id)
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    await db.delete(event)
    await db.commit()
    return {"ok": True}
