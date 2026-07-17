from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import AsyncIterator
import asyncio

from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.api.v1 import clients as clients_module
from app.main import app
from app.models.client import ClientAssignment
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
        self.users = {
            20: SimpleNamespace(id=20, organization_id=1, name="Staff One", email="staff1@example.com", role=UserRole.lawyer, status=RecordStatus.active),
            21: SimpleNamespace(id=21, organization_id=1, name="Staff Two", email="staff2@example.com", role=UserRole.paralegal, status=RecordStatus.active),
            22: SimpleNamespace(id=22, organization_id=1, name="Inactive Staff", email="inactive@example.com", role=UserRole.lawyer, status=RecordStatus.inactive),
            30: SimpleNamespace(id=30, organization_id=2, name="Other Org", email="other@example.com", role=UserRole.lawyer, status=RecordStatus.active),
            99: SimpleNamespace(id=99, organization_id=1, name="Client User", email="client@example.com", role=UserRole.client, status=RecordStatus.active),
        }
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
                occupation="Engineer",
                preferred_contact_method="email",
                date_of_birth=date(1980, 1, 1),
                billing_currency="USD",
                archived_at=None,
                assignments=[],
                created_at=now,
                updated_at=now,
            )
        }
        self.next_id = 2
        self.assignments = []
        self.next_assignment_id = 1
        self.added = []
        self.scalar_queue = []
        self.rolled_back = False

    async def scalar(self, query, *args, **kwargs):
        q = str(query)
        assert "organization_id" in q
        if self.scalar_queue:
            return self.scalar_queue.pop(0)
        if "FROM users" in q:
            return self.user
        if "FROM clients" in q:
            params = query.compile().params
            requested_id = params.get("id_1")
            if requested_id is not None:
                return self.clients.get(requested_id)
            return next(reversed(self.clients.values()), None)
        return None

    async def scalars(self, query, *args, **kwargs):
        q = str(query)
        assert "organization_id" in q
        if "FROM users" in q:
            params = query.compile().params
            requested_ids = next((value for value in params.values() if isinstance(value, (list, tuple, set))), None)
            rows = [user for user in self.users.values() if user.organization_id == 1]
            if requested_ids is not None:
                rows = [user for user in rows if user.id in requested_ids]

            class _Rows:
                def __init__(self, values):
                    self._values = values

                def all(self):
                    return self._values

            return _Rows(rows)

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

    async def execute(self, query, *args, **kwargs):
        q = str(query)
        if "FROM client_assignments" in q:
            params = query.compile().params
            requested_client_id = params.get("client_id_1")
            rows = [a for a in self.assignments if requested_client_id is None or a.client_id == requested_client_id]

            class _Res:
                def __init__(self, values):
                    self._values = values

                def scalars(self):
                    class _Rows:
                        def __init__(self, values):
                            self._values = values

                        def all(self):
                            return self._values

                    return _Rows(self._values)

            return _Res(rows)
        raise AssertionError(f"Unexpected execute query: {q}")

    def add(self, obj):
        if isinstance(obj, ClientAssignment):
            if getattr(obj, "id", None) is None:
                obj.id = self.next_assignment_id
                self.next_assignment_id += 1
            user = self.users[obj.user_id]
            obj.__dict__["user"] = user
            self.assignments.append(obj)
            if obj.client_id in self.clients:
                self.clients[obj.client_id].assignments.append(obj)
            self.added.append(obj)
            return
        if getattr(obj, "id", None) is None:
            obj.id = self.next_id
            self.next_id += 1
        self.clients[obj.id] = obj
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        self.rolled_back = True

    async def refresh(self, obj):
        return None

    async def delete(self, obj):
        if isinstance(obj, ClientAssignment):
            self.assignments = [a for a in self.assignments if a.id != obj.id]
            if obj.client_id in self.clients:
                self.clients[obj.client_id].assignments = [a for a in self.clients[obj.client_id].assignments if a.id != obj.id]
            return
        self.clients.pop(obj.id, None)


def build_client(role: str, db: ClientProfileDBStub, org_id: int = 1, raise_server_exceptions: bool = True):
    user = DummyUser(id=10, organization_id=org_id, name=f"{role} user", email="u@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[ClientProfileDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_create_client_with_typed_fields():
    db = ClientProfileDBStub()
    client = build_client("partner", db, raise_server_exceptions=False)
    try:
        res = client.post("/api/v1/clients", json={
            "name": "Kevin Brown",
            "email": "kevin@example.com",
            "client_type": "corporate",
            "trn_no": "TRN-900",
            "occupation": "Founder",
            "preferred_contact_method": "phone",
            "date_of_birth": "1988-01-02",
            "billing_currency": "AED",
            "notes": "VIP",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["client_type"] == "corporate"
        assert body["trn_no"] == "TRN-900"
        assert body["occupation"] == "Founder"
        assert body["preferred_contact_method"] == "phone"
        assert body["date_of_birth"] == "1988-01-02"
        assert body["billing_currency"] == "AED"
    finally:
        cleanup(client)


def test_create_client_defaults_billing_currency_to_jmd():
    db = ClientProfileDBStub()
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/clients", json={
            "name": "Default Currency Client",
            "email": "default@example.com",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["billing_currency"] == "JMD"
    finally:
        cleanup(client)


def test_update_client_typed_fields_and_archive_sets_archived_at():
    db = ClientProfileDBStub()
    client = build_client("admin", db)
    try:
        res = client.patch("/api/v1/clients/1", json={
            "client_type": "corporate",
            "trn_no": "TRN-UPDATED",
            "occupation": "Managing Director",
            "preferred_contact_method": "whatsapp",
            "date_of_birth": "1990-05-07",
            "billing_currency": "EUR",
            "archived_at": "2026-05-26T10:00:00Z",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["client_type"] == "corporate"
        assert body["trn_no"] == "TRN-UPDATED"
        assert body["occupation"] == "Managing Director"
        assert body["preferred_contact_method"] == "whatsapp"
        assert body["billing_currency"] == "EUR"
        assert body["archived_at"] is not None
    finally:
        cleanup(client)


def test_create_client_accepts_optional_notes_and_team_assignments():
    db = ClientProfileDBStub()
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/clients", json={
            "name": "Taylor Client",
            "email": "taylor@example.com",
            "notes": None,
            "preferred_contact_method": "whatsapp",
            "assigned_user_ids": [20, 21],
        })
        assert res.status_code == 200
        body = res.json()
        assert body["notes"] is None
        assert body["preferred_contact_method"] == "whatsapp"
        assert body["assigned_user_ids"] == [20, 21]
        assert [row["name"] for row in body["assigned_users"]] == ["Staff One", "Staff Two"]
    finally:
        cleanup(client)


def test_update_client_rejects_cross_org_or_client_role_assignments():
    db = ClientProfileDBStub()
    client = build_client("partner", db)
    try:
        res = client.patch("/api/v1/clients/1", json={"assigned_user_ids": [30]})
        assert res.status_code == 400

        res = client.patch("/api/v1/clients/1", json={"assigned_user_ids": [99]})
        assert res.status_code == 400

        res = client.patch("/api/v1/clients/1", json={"assigned_user_ids": [22]})
        assert res.status_code == 400
    finally:
        cleanup(client)


def test_update_client_assignment_sync_adds_removes_and_retains():
    db = ClientProfileDBStub()
    retained = ClientAssignment(client_id=1, user_id=20)
    retained.id = 1
    retained.__dict__["user"] = db.users[20]
    removed = ClientAssignment(client_id=1, user_id=21)
    removed.id = 2
    removed.__dict__["user"] = db.users[21]
    db.assignments = [retained, removed]
    db.clients[1].assignments = [retained, removed]
    client = build_client("admin", db)
    try:
        res = client.patch("/api/v1/clients/1", json={"assigned_user_ids": [20]})
        assert res.status_code == 200
        body = res.json()
        assert body["assigned_user_ids"] == [20]
        assert db.assignments == [retained]
    finally:
        cleanup(client)


def test_assignment_sync_queries_assignments_without_touching_lazy_relationship():
    class LazyClient:
        id = 55

        @property
        def assignments(self):
            raise AssertionError("client.assignments must not be accessed")

    db = ClientProfileDBStub()
    db.assignments = []
    user = db.users[20]

    asyncio.run(clients_module.sync_client_assignments(LazyClient(), [user], db))
    assert [assignment.user_id for assignment in db.assignments] == [20]


def test_create_client_rolls_back_when_assignment_sync_fails(monkeypatch):
    db = ClientProfileDBStub()

    async def fail_sync(*args, **kwargs):
        raise RuntimeError("assignment failure")

    monkeypatch.setattr(clients_module, "sync_client_assignments", fail_sync)
    client = build_client("partner", db, raise_server_exceptions=False)
    try:
        res = client.post("/api/v1/clients", json={"name": "Rollback Client", "assigned_user_ids": [20]})
        assert res.status_code == 500
        assert db.rolled_back is True
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
        for field in ["client_type", "trn_no", "occupation", "preferred_contact_method", "date_of_birth", "billing_currency", "archived_at"]:
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
