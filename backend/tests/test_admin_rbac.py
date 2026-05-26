from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.main import app
from app.models.enums import RecordStatus, UserRole


class AdminDBStub:
    def __init__(self, scalar_values=None, scalars_rows=None):
        self.scalar_values = list(scalar_values or [])
        self.scalars_rows = list(scalars_rows or [])
        self.added = []

    async def scalar(self, *args, **kwargs):
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return None

    async def scalars(self, *args, **kwargs):
        rows = self.scalars_rows.pop(0) if self.scalars_rows else []

        class _Rows:
            def __init__(self, values):
                self._values = values

            def all(self):
                return self._values

        return _Rows(rows)

    async def execute(self, *args, **kwargs):
        class _Res:
            def all(self):
                return []

            def scalars(self):
                class _Rows:
                    def all(self):
                        return []

                return _Rows()

        return _Res()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1
        return None


class DummyUser:
    def __init__(self, role: str, user_id: int = 1, org_id: int = 1):
        now = datetime.now(timezone.utc)
        self.id = user_id
        self.organization_id = org_id
        self.name = f"{role.title()} User"
        self.email = f"{role}@example.com"
        self.role = UserRole(role)
        self.status = RecordStatus.active
        self.created_at = now
        self.updated_at = now


def build_client(role: str, db: AdminDBStub, user_id: int = 1, org_id: int = 1):
    user = DummyUser(role, user_id=user_id, org_id=org_id)

    async def _get_current_user():
        return user

    async def _get_current_org():
        return SimpleNamespace(id=org_id, name="Test Org")

    async def _get_db():
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_current_organization] = _get_current_org
    app.dependency_overrides[deps_module.get_db] = _get_db
    client = TestClient(app)
    return client


def cleanup_client(client):
    client.close()
    app.dependency_overrides.clear()


def user_obj(user_id=2, org_id=1, role="lawyer", status="active"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=user_id,
        organization_id=org_id,
        name="Target User",
        email="target@example.com",
        role=UserRole(role),
        status=RecordStatus(status),
        created_at=now,
        updated_at=now,
    )


def invite_obj(status="pending", expires_delta_hours=48, role="lawyer", org_id=1):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=1,
        organization_id=org_id,
        email="invitee@example.com",
        role=role,
        token="tok",
        status=status,
        expires_at=now + timedelta(hours=expires_delta_hours),
        invited_by=1,
        created_at=now,
    )


def test_partner_can_access_admin_users():
    db = AdminDBStub(scalars_rows=[[user_obj(role="partner")]])
    client = build_client("partner", db)
    try:
        res = client.get("/api/v1/admin/users")
        assert res.status_code == 200
    finally:
        cleanup_client(client)


def test_admin_can_access_admin_users():
    db = AdminDBStub(scalars_rows=[[user_obj(role="admin")]])
    client = build_client("admin", db)
    try:
        res = client.get("/api/v1/admin/users")
        assert res.status_code == 200
    finally:
        cleanup_client(client)


@pytest.mark.parametrize("role", ["lawyer", "paralegal", "client"])
def test_non_admin_roles_blocked_from_admin_users(role):
    db = AdminDBStub()
    client = build_client(role, db)
    try:
        assert client.get("/api/v1/admin/users").status_code == 403
    finally:
        cleanup_client(client)


@pytest.mark.parametrize("role", ["partner", "admin"])
def test_partner_admin_can_create_invite(role):
    db = AdminDBStub(scalar_values=[None])
    client = build_client(role, db)
    try:
        res = client.post("/api/v1/admin/invites", json={"email": "new@example.com", "role": "lawyer"})
        assert res.status_code == 200
    finally:
        cleanup_client(client)


@pytest.mark.parametrize("role", ["lawyer", "paralegal", "client"])
def test_non_admin_roles_blocked_from_creating_invites(role):
    db = AdminDBStub()
    client = build_client(role, db)
    try:
        res = client.post("/api/v1/admin/invites", json={"email": "new@example.com", "role": "lawyer"})
        assert res.status_code == 403
    finally:
        cleanup_client(client)


def test_cannot_deactivate_self():
    self_user = user_obj(user_id=1, role="partner")
    db = AdminDBStub(scalar_values=[self_user])
    client = build_client("partner", db, user_id=1)
    try:
        res = client.delete("/api/v1/admin/users/1")
        assert res.status_code == 400
    finally:
        cleanup_client(client)


def test_cannot_deactivate_last_active_partner():
    target = user_obj(user_id=2, role="partner", status="active")
    db = AdminDBStub(scalar_values=[target, 1])
    client = build_client("partner", db, user_id=1)
    try:
        res = client.delete("/api/v1/admin/users/2")
        assert res.status_code == 400
    finally:
        cleanup_client(client)


def test_cannot_deactivate_last_active_admin():
    target = user_obj(user_id=3, role="admin", status="active")
    db = AdminDBStub(scalar_values=[target, 1])
    client = build_client("partner", db, user_id=1)
    try:
        res = client.delete("/api/v1/admin/users/3")
        assert res.status_code == 400
    finally:
        cleanup_client(client)


def test_accept_invite_rejects_invalid_token():
    db = AdminDBStub(scalar_values=[None])
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/auth/accept-invite", json={"token": "bad", "name": "New", "password": "secret123"})
        assert res.status_code == 400
    finally:
        cleanup_client(client)


def test_accept_invite_rejects_expired_invite():
    inv = invite_obj(status="pending", expires_delta_hours=-1)
    db = AdminDBStub(scalar_values=[inv])
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/auth/accept-invite", json={"token": "tok", "name": "New", "password": "secret123"})
        assert res.status_code == 400
    finally:
        cleanup_client(client)


def test_accept_invite_rejects_cancelled_invite():
    inv = invite_obj(status="expired", expires_delta_hours=24)
    db = AdminDBStub(scalar_values=[inv])
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/auth/accept-invite", json={"token": "tok", "name": "New", "password": "secret123"})
        assert res.status_code == 400
    finally:
        cleanup_client(client)


def test_accept_invite_creates_user_with_correct_org_and_role():
    inv = invite_obj(status="pending", expires_delta_hours=24, role="paralegal", org_id=5)
    db = AdminDBStub(scalar_values=[inv, None])
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/auth/accept-invite", json={"token": "tok", "name": "New Joiner", "password": "secret123"})
        assert res.status_code == 200
        created_user = db.added[0]
        assert created_user.organization_id == 5
        assert created_user.role == UserRole.paralegal
    finally:
        cleanup_client(client)


def test_cross_org_admin_user_access_hidden_or_blocked():
    db = AdminDBStub(scalar_values=[None])
    client = build_client("partner", db, org_id=1)
    try:
        res = client.patch("/api/v1/admin/users/999", json={"role": "lawyer"})
        assert res.status_code == 404
    finally:
        cleanup_client(client)


def test_cross_org_invite_access_hidden_or_blocked():
    db = AdminDBStub(scalar_values=[None])
    client = build_client("admin", db, org_id=1)
    try:
        res = client.post("/api/v1/admin/invites/999/cancel")
        assert res.status_code == 404
    finally:
        cleanup_client(client)
