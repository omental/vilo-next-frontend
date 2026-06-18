from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.api.v1 import reports as reports_module
from app.main import app
from app.models.enums import RecordStatus, UserRole


class DummyUser(SimpleNamespace):
    pass


class DummyDB:
    pass


def build_client(role: str):
    user = DummyUser(
        id=5,
        organization_id=1,
        name=role,
        email="user@example.com",
        role=UserRole(role),
        status=RecordStatus.active,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = DummyDB()

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[DummyDB]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_revenue_by_staff_endpoint_uses_collected_revenue_source(monkeypatch):
    captured = {}

    async def _fake_report(db, **kwargs):
        captured.update(kwargs)
        return [{
            "staff_user_id": 7,
            "staff_name": "Lawyer A",
            "currency": "USD",
            "total_billed": 500,
            "total_collected": 300,
            "invoice_count": 2,
            "direct_collected": 200,
            "trust_collected": 100,
        }]

    monkeypatch.setattr(reports_module, "build_revenue_by_staff_report", _fake_report)
    client = build_client("partner")
    try:
        res = client.get("/api/v1/reports/billing/revenue-by-staff?staff_user_id=7&currency=USD")
        assert res.status_code == 200
        body = res.json()
        assert body[0]["total_collected"] == "300"
        assert body[0]["trust_collected"] == "100"
        assert captured["organization_id"] == 1
        assert captured["staff_user_id"] == 7
        assert captured["currency"] == "USD"
    finally:
        cleanup(client)


def test_time_by_staff_endpoint_uses_time_entry_source(monkeypatch):
    captured = {}

    async def _fake_report(db, **kwargs):
        captured.update(kwargs)
        return [{
            "staff_user_id": 7,
            "staff_name": "Lawyer A",
            "currency": "USD",
            "total_hours": 4,
            "billable_hours": 4,
            "estimated_value": 900,
        }]

    monkeypatch.setattr(reports_module, "build_time_by_staff_report", _fake_report)
    client = build_client("lawyer")
    try:
        res = client.get("/api/v1/reports/billing/time-by-staff?staff_user_id=7")
        assert res.status_code == 200
        body = res.json()
        assert body[0]["estimated_value"] == "900"
        assert body[0]["billable_hours"] == "4"
        assert captured["organization_id"] == 1
        assert captured["staff_user_id"] == 7
    finally:
        cleanup(client)


def test_client_cannot_access_billing_reports():
    client = build_client("client")
    try:
        res = client.get("/api/v1/reports/billing/revenue-by-staff")
        assert res.status_code == 403
    finally:
        cleanup(client)
