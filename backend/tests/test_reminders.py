from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.notification import Notification
from app.services.reminders import process_due_reminders


class ReminderDBStub:
    def __init__(self, scalars_rows=None, existing=False):
        self.scalars_rows = list(scalars_rows or [])
        self.existing = existing
        self.added = []
        self.commits = 0

    async def scalar(self, *args, **kwargs):
        return 1 if self.existing else None

    async def scalars(self, *args, **kwargs):
        rows = self.scalars_rows.pop(0) if self.scalars_rows else []

        class _Rows:
            def __init__(self, values):
                self._values = values

            def all(self):
                return self._values

        return _Rows(rows)

    def add(self, obj):
        if isinstance(obj, Notification):
            obj.id = len(self.added) + 1
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def event_obj(event_id=10, org_id=1, user_id=2, start_at=None, reminder_at=None):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=event_id,
        organization_id=org_id,
        case_id=None,
        created_by=user_id,
        title="Hearing",
        start_at=start_at or now,
        reminder_at=reminder_at,
    )


def task_obj(task_id=20, org_id=1, creator_id=2, assigned_to=3, due_date=None, reminder_at=None, status="not_started"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=task_id,
        organization_id=org_id,
        case_id=30,
        client_id=40,
        created_by=creator_id,
        assigned_to=assigned_to,
        title="File response",
        due_date=due_date or now,
        reminder_at=reminder_at,
        archived_at=None,
        status=status,
    )


@pytest.mark.asyncio
async def test_due_event_and_task_reminders_create_notifications_with_links():
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    event = event_obj(start_at=now - timedelta(minutes=1), reminder_at=now - timedelta(minutes=15))
    task = task_obj(due_date=now - timedelta(minutes=1), reminder_at=now - timedelta(minutes=10))
    db = ReminderDBStub(scalars_rows=[[event], [event], [task], [task]])

    created = await process_due_reminders(db, now=now)

    assert created == 6
    types = {row.type for row in db.added}
    assert {"event_due", "event_reminder", "task_due", "task_reminder"} <= types
    assert any(row.metadata_json.get("link") == "/dashboard/calendar?event_id=10" for row in db.added)
    assert any(row.metadata_json.get("link") == "/dashboard/tasks/20" for row in db.added)
    assert all(row.organization_id == 1 for row in db.added)
    assert all(row.is_read is False for row in db.added)


@pytest.mark.asyncio
async def test_reminders_are_idempotent_when_existing_dedupe_keys_are_found():
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    event = event_obj(start_at=now - timedelta(minutes=1), reminder_at=now - timedelta(minutes=15))
    task = task_obj(due_date=now - timedelta(days=1), reminder_at=now - timedelta(minutes=10))
    db = ReminderDBStub(scalars_rows=[[event], [event], [task], [task]], existing=True)

    created = await process_due_reminders(db, now=now)

    assert created == 0
    assert db.added == []


@pytest.mark.asyncio
async def test_overdue_task_notification_uses_overdue_type_after_due_day():
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    task = task_obj(due_date=now - timedelta(days=1), reminder_at=None)
    db = ReminderDBStub(scalars_rows=[[], [], [task], []])

    created = await process_due_reminders(db, now=now)

    assert created == 2
    assert {row.type for row in db.added} == {"task_overdue"}
