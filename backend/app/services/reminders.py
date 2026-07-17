from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_event import CalendarEvent
from app.models.case import CaseAssignment
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.services.notifications import create_notification


REMINDER_POLL_INTERVAL_SECONDS = 60
OPEN_TASK_STATUSES = {"not_started", "in_progress", "waiting", "pending"}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _display_time(value: datetime | None) -> str:
    converted = _utc(value)
    if converted is None:
        return "unscheduled"
    return converted.strftime("%Y-%m-%d %H:%M UTC")


def _event_link(event: CalendarEvent) -> str:
    return f"/dashboard/calendar?event_id={event.id}"


def _task_link(task: Task) -> str:
    return f"/dashboard/tasks/{task.id}"


async def _already_created(db: AsyncSession, *, organization_id: int, user_id: int, dedupe_key: str) -> bool:
    existing = await db.scalar(
        select(Notification.id).where(
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.dedupe_key == dedupe_key,
        )
    )
    return existing is not None


async def _event_recipient_ids(db: AsyncSession, event: CalendarEvent) -> list[int]:
    user_ids = {event.created_by}
    if event.case_id:
        rows = await db.scalars(select(CaseAssignment.user_id).where(CaseAssignment.case_id == event.case_id))
        user_ids.update(rows.all())
    return sorted(user_ids)


def _task_recipient_ids(task: Task) -> list[int]:
    user_ids = {task.created_by}
    if task.assigned_to:
        user_ids.add(task.assigned_to)
    return sorted(user_ids)


async def _create_once(
    db: AsyncSession,
    *,
    organization_id: int,
    user_id: int,
    type: str,
    title: str,
    body: str,
    metadata_json: dict,
    dedupe_key: str,
) -> bool:
    if await _already_created(db, organization_id=organization_id, user_id=user_id, dedupe_key=dedupe_key):
        return False
    await create_notification(
        db,
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        metadata_json=metadata_json,
        dedupe_key=dedupe_key,
    )
    return True


async def process_due_reminders(db: AsyncSession, *, now: datetime | None = None) -> int:
    current_time = _utc(now) or datetime.now(timezone.utc)
    created = 0

    event_rows = (
        await db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.start_at <= current_time,
            )
        )
    ).all()
    event_reminder_rows = (
        await db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.reminder_at.is_not(None),
                CalendarEvent.reminder_at <= current_time,
            )
        )
    ).all()

    tasks_due_rows = (
        await db.scalars(
            select(Task).where(
                Task.due_date.is_not(None),
                Task.due_date <= current_time,
                Task.archived_at.is_(None),
                Task.status.in_(OPEN_TASK_STATUSES),
            )
        )
    ).all()
    task_reminder_rows = (
        await db.scalars(
            select(Task).where(
                Task.reminder_at.is_not(None),
                Task.reminder_at <= current_time,
                Task.archived_at.is_(None),
                Task.status.in_(OPEN_TASK_STATUSES),
            )
        )
    ).all()

    for event in event_rows:
        for user_id in await _event_recipient_ids(db, event):
            key = f"calendar_event:{event.id}:start:{_display_time(event.start_at)}"
            created += int(
                await _create_once(
                    db,
                    organization_id=event.organization_id,
                    user_id=user_id,
                    type="event_due",
                    title=f"Event starting: {event.title}",
                    body=f"Start time: {_display_time(event.start_at)}",
                    metadata_json={
                        "calendar_event_id": event.id,
                        "case_id": event.case_id,
                        "starts_at": _utc(event.start_at).isoformat() if _utc(event.start_at) else None,
                        "link": _event_link(event),
                    },
                    dedupe_key=key,
                )
            )

    for event in event_reminder_rows:
        for user_id in await _event_recipient_ids(db, event):
            key = f"calendar_event:{event.id}:reminder:{_display_time(event.reminder_at)}"
            created += int(
                await _create_once(
                    db,
                    organization_id=event.organization_id,
                    user_id=user_id,
                    type="event_reminder",
                    title=f"Event reminder: {event.title}",
                    body=f"Start time: {_display_time(event.start_at)}",
                    metadata_json={
                        "calendar_event_id": event.id,
                        "case_id": event.case_id,
                        "starts_at": _utc(event.start_at).isoformat() if _utc(event.start_at) else None,
                        "reminder_at": _utc(event.reminder_at).isoformat() if _utc(event.reminder_at) else None,
                        "link": _event_link(event),
                    },
                    dedupe_key=key,
                )
            )

    for task in tasks_due_rows:
        overdue = _utc(task.due_date).date() < current_time.date() if _utc(task.due_date) else False
        for user_id in _task_recipient_ids(task):
            kind = "overdue" if overdue else "due"
            key = f"task:{task.id}:{kind}:{_display_time(task.due_date)}"
            created += int(
                await _create_once(
                    db,
                    organization_id=task.organization_id,
                    user_id=user_id,
                    type="task_overdue" if overdue else "task_due",
                    title=f"Task {'overdue' if overdue else 'due'}: {task.title}",
                    body=f"Due time: {_display_time(task.due_date)}",
                    metadata_json={
                        "task_id": task.id,
                        "case_id": task.case_id,
                        "client_id": task.client_id,
                        "due_date": _utc(task.due_date).isoformat() if _utc(task.due_date) else None,
                        "link": _task_link(task),
                    },
                    dedupe_key=key,
                )
            )

    for task in task_reminder_rows:
        for user_id in _task_recipient_ids(task):
            key = f"task:{task.id}:reminder:{_display_time(task.reminder_at)}"
            created += int(
                await _create_once(
                    db,
                    organization_id=task.organization_id,
                    user_id=user_id,
                    type="task_reminder",
                    title=f"Task reminder: {task.title}",
                    body=f"Due time: {_display_time(task.due_date)}",
                    metadata_json={
                        "task_id": task.id,
                        "case_id": task.case_id,
                        "client_id": task.client_id,
                        "due_date": _utc(task.due_date).isoformat() if _utc(task.due_date) else None,
                        "reminder_at": _utc(task.reminder_at).isoformat() if _utc(task.reminder_at) else None,
                        "link": _task_link(task),
                    },
                    dedupe_key=key,
                )
            )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return 0

    return created
