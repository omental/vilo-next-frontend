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


class ClientProfileDBStub:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.user = SimpleNamespace(id=77, organization_id=1, role=UserRole.client)
        self.clients = {
            1: SimpleNamespace(
                id=1,
                organization_id=1,
                name="John Smith",
                email="john@example.com",
                phone="+123",
                user_id=None,
                address="Main St",
                notes="Original notes",
                client_type="individual",
                trn_no="TRN-1",
                preferred_contact_method="email",
                date_of_birth=date(1980, 1, 1),
                billing_currency="USD",
                archived_at=None,
                created_at=now,
                updated_at=now,
            )
        }
        self.next_id = 2
        self.added = []
        self.scalar_queue = []

    async def scalar(self, query, *args, **kwargs):
        q = str(query)
        assert "organization_id" in q
        if self.scalar_queue:
            return self.scalar_queue.pop(0)
        if "FROM users" in q:
            return self.user
        if "FROM clients" in q:
            return next(iter(self.clients.values()), None)
        return None

    async def scalars(self, query, *args, **kwargs):
        q = str(query)
        assert "organization_id" in q
        rows = list(self.clients.values())
        if "clients.archived_at IS NULL" in q:
            rows = [c for c in rows if c.archived_at is None]
        if "clients.archived_at IS NOT NULL" in q:
            rows = [c for c in rows if c.archived_at is not None]

        class _Rows:
            def __init__(self, values):
                self._values = values

            def all(self):
                return self._values

        return _Rows(rows)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = self.next_id
            self.next_id += 1
        self.clients[obj.id] = obj
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None

    async def delete(self, obj):
        self.clients.pop(obj.id, None)


def build_client(role: str, db: ClientProfileDBStub, org_id: int = 1):
    user = DummyUser(id=10, organization_id=org_id, name=f"{role} user", email="u@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[ClientProfileDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_create_client_with_typed_fields():
    db = ClientProfileDBStub()
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/clients", json={
            "name": "Kevin Brown",
            "email": "kevin@example.com",
            "client_type": "corporate",
            "trn_no": "TRN-900",
            "preferred_contact_method": "phone",
            "date_of_birth": "1988-01-02",
            "billing_currency": "AED",
            "notes": "VIP",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["client_type"] == "corporate"
        assert body["trn_no"] == "TRN-900"
        assert body["preferred_contact_method"] == "phone"
        assert body["date_of_birth"] == "1988-01-02"
        assert body["billing_currency"] == "AED"
    finally:
        cleanup(client)


def test_update_client_typed_fields_and_archive_sets_archived_at():
    db = ClientProfileDBStub()
    client = build_client("admin", db)
    try:
        res = client.patch("/api/v1/clients/1", json={
            "client_type": "corporate",
            "trn_no": "TRN-UPDATED",
            "preferred_contact_method": "sms",
            "date_of_birth": "1990-05-07",
            "billing_currency": "EUR",
            "archived_at": "2026-05-26T10:00:00Z",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["client_type"] == "corporate"
        assert body["trn_no"] == "TRN-UPDATED"
        assert body["preferred_contact_method"] == "sms"
        assert body["billing_currency"] == "EUR"
        assert body["archived_at"] is not None
    finally:
        cleanup(client)


def test_get_client_returns_new_fields():
    db = ClientProfileDBStub()
    db.scalar_queue = [db.clients[1]]
    client = build_client("lawyer", db)
    try:
        res = client.get("/api/v1/clients/1")
        assert res.status_code == 200
        body = res.json()
        for field in ["client_type", "trn_no", "preferred_contact_method", "date_of_birth", "billing_currency", "archived_at"]:
            assert field in body
    finally:
        cleanup(client)


def test_list_clients_status_filter_active_archived():
    db = ClientProfileDBStub()
    db.clients[1].archived_at = datetime(2026, 5, 26, tzinfo=timezone.utc)
    db.clients[2] = SimpleNamespace(**{**db.clients[1].__dict__, "id": 2, "name": "Active User", "archived_at": None})

    client = build_client("partner", db)
    try:
        active = client.get("/api/v1/clients?status=active")
        archived = client.get("/api/v1/clients?status=archived")
        assert active.status_code == 200
        assert archived.status_code == 200
        assert all(row["archived_at"] is None for row in active.json())
        assert all(row["archived_at"] is not None for row in archived.json())
    finally:
        cleanup(client)


def test_cross_org_access_blocked_for_get():
    db = ClientProfileDBStub()
    db.scalar_queue = [None]
    client = build_client("partner", db, org_id=1)
    try:
        res = client.get("/api/v1/clients/999")
        assert res.status_code == 404
    finally:
        cleanup(client)


def test_client_role_cannot_mutate_internal_clients_route():
    db = ClientProfileDBStub()
    client = build_client("client", db)
    try:
        res = client.post("/api/v1/clients", json={"name": "Blocked"})
        assert res.status_code == 403
    finally:
        cleanup(client)
