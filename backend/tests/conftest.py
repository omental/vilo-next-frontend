from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import AsyncIterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.api.v1 import portal as portal_module
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


class DummyDB:
    """Minimal async DB stub for access-control tests."""

    def __init__(self):
        self._scalar = None
        self._scalars = []
        self._execute_rows = []

    async def scalar(self, *args, **kwargs):
        return self._scalar

    async def scalars(self, *args, **kwargs):
        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Rows(self._scalars)

    async def execute(self, *args, **kwargs):
        class _Res:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                class _Rows:
                    def __init__(self, rows):
                        self._rows = rows

                    def all(self):
                        return self._rows

                return _Rows(self._rows)

            def scalar_one_or_none(self):
                return self._rows[0] if self._rows else None

            def all(self):
                return self._rows

        return _Res(self._execute_rows)


@pytest.fixture
def role_user_factory():
    def _make(role: str, org_id: int = 1, user_id: int = 1) -> DummyUser:
        return DummyUser(
            id=user_id,
            organization_id=org_id,
            name=f"{role.title()} User",
            email=f"{role}@example.com",
            role=UserRole(role),
        )

    return _make


@pytest.fixture
def client_for_user(role_user_factory):
    created_clients: list[TestClient] = []

    def _build(role: str, *, linked_client: bool = True) -> TestClient:
        user = role_user_factory(role)
        db = DummyDB()

        async def _get_current_user():
            return user

        async def _get_current_org(current_user=user):
            return SimpleNamespace(id=current_user.organization_id, name="Test Org")

        async def _get_db() -> AsyncIterator[DummyDB]:
            yield db

        async def _portal_client(_db, _user):
            if _user.role != UserRole.client:
                raise HTTPException(status_code=403, detail="Client portal only")
            if not linked_client:
                raise HTTPException(status_code=403, detail="Client profile not linked")
            return SimpleNamespace(id=10, organization_id=_user.organization_id, user_id=_user.id, name="Client A", email="c@example.com", phone=None, address=None, notes=None)

        app.dependency_overrides[deps_module.get_current_user] = _get_current_user
        app.dependency_overrides[deps_module.get_current_organization] = _get_current_org
        app.dependency_overrides[deps_module.get_db] = _get_db

        original_portal_client = portal_module.get_portal_client
        portal_module.get_portal_client = _portal_client

        test_client = TestClient(app)
        test_client._dummy_db = db  # type: ignore[attr-defined]
        test_client._restore_portal = original_portal_client  # type: ignore[attr-defined]
        created_clients.append(test_client)
        return test_client

    yield _build

    for tc in created_clients:
        portal_module.get_portal_client = tc._restore_portal  # type: ignore[attr-defined]
        tc.close()
    app.dependency_overrides.clear()
