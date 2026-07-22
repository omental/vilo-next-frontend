from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.main import app
from app.models.enums import RecordStatus, UserRole


@dataclass
class DummyUser:
    id: int
    organization_id: int
    name: str
    email: str
    role: UserRole
    status: RecordStatus = RecordStatus.active
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)


class CalendarDBStub:
    def __init__(self, scalar_values=None, scalars_rows=None):
        self.scalar_values = list(scalar_values or [])
        self.scalars_rows = list(scalars_rows or [])
        self.added = []

    async def scalar(self, query, *args, **kwargs):
        assert "organization_id" in str(query)
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return None

    async def scalars(self, query, *args, **kwargs):
        assert "organization_id" in str(query)
        rows = self.scalars_rows.pop(0) if self.scalars_rows else []

        class _Rows:
            def __init__(self, values):
                self._values = values

            def all(self):
                return self._values

        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for idx, obj in enumerate(self.added, start=1):
            if getattr(obj, "id", None) is None:
                obj.id = idx

    async def commit(self):
        return None

    async def execute(self, query, *args, **kwargs):
        return None

    async def refresh(self, obj):
        return None


def build_client(role: str, db: CalendarDBStub, org_id: int = 1):
    user = DummyUser(id=1, organization_id=org_id, name=f"{role} user", email="u@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[CalendarDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def _event(event_id=5, org_id=1):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=event_id,
        organization_id=org_id,
        case_id=None,
        created_by=1,
        title="Court Hearing",
        description=None,
        event_type="court",
        start_at=now,
        end_at=None,
        location=None,
        created_at=now,
        updated_at=now,
    )


def test_staff_can_list_org_scoped_calendar_events():
    db = CalendarDBStub(scalars_rows=[[_event()]])
    client = build_client("lawyer", db)
    try:
        res = client.get("/api/v1/calendar/events")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["event_type"] == "court"
    finally:
        cleanup(client)


def test_staff_can_create_calendar_event_with_figma_types():
    db = CalendarDBStub(scalar_values=[None])
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/calendar/events", json={
            "title": "Travel briefing",
            "event_type": "travel",
            "start_at": "2026-05-26T09:00:00Z",
            "end_at": "2026-05-26T10:00:00Z",
            "case_id": None,
        })
        assert res.status_code == 200
        assert res.json()["event_type"] == "travel"
    finally:
        cleanup(client)


def test_cross_org_event_access_is_blocked():
    db = CalendarDBStub(scalar_values=[None])
    client = build_client("admin", db)
    try:
        res = client.get("/api/v1/calendar/events/999")
        assert res.status_code == 404
    finally:
        cleanup(client)


def test_client_role_cannot_mutate_calendar_events():
    db = CalendarDBStub()
    client = build_client("client", db)
    try:
        res = client.post("/api/v1/calendar/events", json={"title": "x", "event_type": "note", "start_at": "2026-05-26T09:00:00Z"})
        assert res.status_code == 403
    finally:
        cleanup(client)
