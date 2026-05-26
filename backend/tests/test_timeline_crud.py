from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
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


class TimelineDBStub:
    def __init__(self, scalar_values=None, timeline_rows=None):
        self.scalar_values = list(scalar_values or [])
        self.timeline_rows = list(timeline_rows or [])
        self.added = []
        self.deleted = []

    async def scalar(self, *args, **kwargs):
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return None

    async def scalars(self, *args, **kwargs):
        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Rows(self.timeline_rows)

    async def execute(self, *args, **kwargs):
        class _Res:
            def __init__(self):
                self._rows = []

            def all(self):
                return self._rows

        return _Res()

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        for idx, obj in enumerate(self.added, start=1):
            if getattr(obj, "id", None) is None:
                obj.id = idx

    async def commit(self):
        return None

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1
        return None


def build_client(role: str, db: TimelineDBStub, org_id: int = 1):
    user = DummyUser(id=1, organization_id=org_id, name=f"{role} user", email="u@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[TimelineDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def _case(org_id=1, case_id=9):
    return SimpleNamespace(id=case_id, organization_id=org_id, assignments=[])


def _event(org_id=1, case_id=9, event_id=22, title="Case Filed"):
    return SimpleNamespace(
        id=event_id,
        organization_id=org_id,
        case_id=case_id,
        actor_id=1,
        event_type="milestone",
        title=title,
        description="desc",
        metadata_json={"status": "active", "completed": False, "event_date": "2026-01-02", "locked": False},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_timeline_list_allowed_for_staff_role_and_scoped():
    db = TimelineDBStub(scalar_values=[_case()], timeline_rows=[_event()])
    client = build_client("lawyer", db, org_id=1)
    try:
        res = client.get("/api/v1/cases/9/timeline")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["case_id"] == 9
        assert body[0]["event_type"] == "milestone"
    finally:
        cleanup(client)


def test_timeline_create_update_delete_allowed_for_staff():
    db = TimelineDBStub(scalar_values=[_case(), _case(), _event(), _case(), _event()])
    client = build_client("partner", db, org_id=1)
    try:
        create_res = client.post("/api/v1/cases/9/timeline", json={
            "title": "Hearing #1",
            "event_type": "hearing",
            "event_date": "2026-02-10",
            "completed": False,
            "status": "active",
            "description": "Initial hearing",
        })
        assert create_res.status_code == 200

        update_res = client.patch("/api/v1/cases/9/timeline/22", json={"status": "inactive", "completed": True})
        assert update_res.status_code == 200

        delete_res = client.delete("/api/v1/cases/9/timeline/22")
        assert delete_res.status_code == 200
        assert delete_res.json()["ok"] is True
    finally:
        cleanup(client)


def test_timeline_cross_org_access_blocked_by_case_lookup():
    db = TimelineDBStub(scalar_values=[None])
    client = build_client("admin", db, org_id=1)
    try:
        res = client.get("/api/v1/cases/999/timeline")
        assert res.status_code == 404
    finally:
        cleanup(client)


def test_timeline_mutation_blocked_for_client_role():
    db = TimelineDBStub()
    client = build_client("client", db, org_id=1)
    try:
        res = client.post("/api/v1/cases/9/timeline", json={"title": "x", "event_type": "milestone"})
        assert res.status_code == 403
    finally:
        cleanup(client)


def test_timeline_filters_apply_to_results():
    rows = [
        _event(event_id=1, title="First Hearing"),
        SimpleNamespace(
            id=2,
            organization_id=1,
            case_id=9,
            actor_id=1,
            event_type="filing",
            title="Tax filing",
            description="Submitted",
            metadata_json={"status": "inactive", "completed": True, "event_date": "2026-03-15", "locked": False},
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        ),
    ]
    db = TimelineDBStub(scalar_values=[_case()], timeline_rows=rows)
    client = build_client("lawyer", db, org_id=1)
    try:
        res = client.get("/api/v1/cases/9/timeline?search=tax&event_type=filing&status=inactive&completed=true&date_from=2026-03-01&date_to=2026-03-31")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["title"] == "Tax filing"
    finally:
        cleanup(client)
