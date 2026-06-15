from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
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


def case_obj(org_id: int = 1, case_id: int = 21, client_id: int = 31, title: str = "Brown v. State"):
    return SimpleNamespace(id=case_id, organization_id=org_id, client_id=client_id, title=title, client=None)


def client_obj(org_id: int = 1, client_id: int = 31, name: str = "Kevin Brown"):
    return SimpleNamespace(id=client_id, organization_id=org_id, name=name)


def staff_obj(org_id: int = 1, user_id: int = 7, name: str = "Jordan Hale"):
    return SimpleNamespace(id=user_id, organization_id=org_id, role=UserRole.lawyer, name=name)


def invoice_obj(org_id: int = 1, invoice_id: int = 88, client_id: int = 31, case_id: int | None = 21):
    return SimpleNamespace(id=invoice_id, organization_id=org_id, client_id=client_id, case_id=case_id, invoice_number="INV-2026-0008")


def time_entry_obj(
    *,
    entry_id: int = 501,
    org_id: int = 1,
    case=None,
    client=None,
    staff=None,
    invoice=None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    duration_minutes: int = 90,
    billing_type: str = "professional_fee",
    hourly_rate: Decimal | None = Decimal("250.00"),
    amount: Decimal = Decimal("375.00"),
    status: str = "billable",
):
    now = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
    case = case or case_obj(org_id=org_id)
    client = client or client_obj(org_id=org_id, client_id=case.client_id)
    staff = staff or staff_obj(org_id=org_id)
    return SimpleNamespace(
        id=entry_id,
        organization_id=org_id,
        case_id=case.id if case else None,
        client_id=client.id if client else None,
        user_id=staff.id,
        invoice_id=invoice.id if invoice else None,
        description="Draft witness prep",
        start_time=start_time or datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        end_time=end_time or datetime(2026, 6, 15, 10, 30, tzinfo=timezone.utc),
        duration_minutes=duration_minutes,
        billing_type=billing_type,
        hourly_rate=hourly_rate,
        amount=amount,
        status=status,
        created_at=now,
        updated_at=now,
        case=case,
        client=client,
        user=staff,
        invoice=invoice,
    )


class TimeEntryDBStub:
    def __init__(self):
        self.case_obj = case_obj()
        self.client_obj = client_obj()
        self.user_obj = staff_obj()
        self.invoice_obj = None
        self.time_entry_obj = time_entry_obj(case=self.case_obj, client=self.client_obj, staff=self.user_obj)
        self.time_entry_rows = [self.time_entry_obj]
        self.total = 1
        self.linked_line_item_id = None
        self.added = []
        self.deleted = []

    async def scalar(self, query, *args, **kwargs):
        q = str(query)
        if "count(time_entries.id)" in q.lower():
            assert "organization_id" in q
            return self.total
        if "FROM time_entries" in q:
            assert "organization_id" in q
            return self.time_entry_obj
        if "FROM cases" in q:
            return self.case_obj
        if "FROM clients" in q:
            return self.client_obj
        if "FROM users" in q:
            return self.user_obj
        if "FROM invoices" in q:
            return self.invoice_obj
        if "FROM invoice_line_items" in q:
            return self.linked_line_item_id
        return None

    async def scalars(self, query, *args, **kwargs):
        q = str(query)
        if "FROM time_entries" in q:
            assert "organization_id" in q

        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        if "FROM time_entries" in q:
            return _Rows(self.time_entry_rows)
        return _Rows([])

    def add(self, obj):
        self.added.append(obj)
        if obj.__class__.__name__ == "TimeEntry":
            self.time_entry_obj = time_entry_obj(
                entry_id=501,
                org_id=obj.organization_id,
                case=self.case_obj if obj.case_id else None,
                client=self.client_obj if obj.client_id else None,
                staff=self.user_obj,
                invoice=self.invoice_obj if obj.invoice_id else None,
                start_time=obj.start_time,
                end_time=obj.end_time,
                duration_minutes=obj.duration_minutes,
                billing_type=obj.billing_type,
                hourly_rate=obj.hourly_rate,
                amount=obj.amount,
                status=obj.status,
            )

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        for idx, obj in enumerate(self.added, start=501):
            if getattr(obj, "id", None) is None:
                obj.id = idx

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


def build_client(role: str, db: TimeEntryDBStub, org_id: int = 1):
    user = DummyUser(id=7, organization_id=org_id, name=f"{role} user", email="staff@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[TimeEntryDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_staff_can_create_time_entry_in_own_org():
    db = TimeEntryDBStub()
    client = build_client("lawyer", db)
    try:
        res = client.post("/api/v1/time-entries", json={
            "case_id": 21,
            "description": "Hearing prep",
            "start_time": "2026-06-15T09:00:00Z",
            "end_time": "2026-06-15T11:00:00Z",
            "billing_type": "professional_fee",
            "hourly_rate": "250.00",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["organization_id"] == 1
        assert body["duration_minutes"] == 120
        assert body["amount"] == "500.00"
        assert body["client_name"] == "Kevin Brown"
    finally:
        cleanup(client)


def test_list_time_entries_is_org_scoped_and_paginated():
    db = TimeEntryDBStub()
    client = build_client("partner", db)
    try:
        res = client.get("/api/v1/time-entries?page=1&per_page=10")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["page"] == 1
        assert body["items"][0]["id"] == 501
    finally:
        cleanup(client)


def test_cross_org_case_cannot_be_linked():
    db = TimeEntryDBStub()
    db.case_obj = None
    client = build_client("admin", db)
    try:
        res = client.post("/api/v1/time-entries", json={
            "case_id": 999,
            "description": "Cross org attempt",
            "start_time": "2026-06-15T09:00:00Z",
            "end_time": "2026-06-15T10:00:00Z",
            "billing_type": "professional_fee",
            "hourly_rate": "200.00",
        })
        assert res.status_code == 400
        assert "Case must belong to your organization" in res.json()["detail"]
    finally:
        cleanup(client)


def test_cross_org_time_entry_access_is_hidden():
    db = TimeEntryDBStub()
    db.time_entry_obj = None
    client = build_client("paralegal", db)
    try:
        res = client.get("/api/v1/time-entries/999")
        assert res.status_code == 404
    finally:
        cleanup(client)


def test_update_recalculates_amount_and_duration():
    db = TimeEntryDBStub()
    db.time_entry_obj = time_entry_obj()
    client = build_client("partner", db)
    try:
        res = client.patch("/api/v1/time-entries/501", json={
            "start_time": "2026-06-15T09:00:00Z",
            "end_time": "2026-06-15T12:00:00Z",
            "hourly_rate": "300.00",
            "billing_type": "professional_fee",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["duration_minutes"] == 180
        assert body["amount"] == "900.00"
    finally:
        cleanup(client)


def test_delete_allows_non_invoiced_entry_and_blocks_linked_entry():
    db = TimeEntryDBStub()
    client = build_client("lawyer", db)
    try:
        allowed = client.delete("/api/v1/time-entries/501")
        assert allowed.status_code == 200
        assert allowed.json()["ok"] is True
        assert db.deleted

        db.time_entry_obj = time_entry_obj(invoice=invoice_obj(), billing_type="invoiced", status="invoiced")
        blocked = client.delete("/api/v1/time-entries/501")
        assert blocked.status_code == 409
    finally:
        cleanup(client)


def test_non_billable_amounts_zero_and_invalid_time_order_blocked():
    db = TimeEntryDBStub()
    client = build_client("admin", db)
    try:
        non_billable = client.post("/api/v1/time-entries", json={
            "case_id": 21,
            "description": "Internal review",
            "start_time": "2026-06-15T09:00:00Z",
            "end_time": "2026-06-15T09:45:00Z",
            "billing_type": "non_billable",
        })
        assert non_billable.status_code == 200
        body = non_billable.json()
        assert body["amount"] == "0.00"
        assert body["status"] == "non_billable"

        invalid = client.post("/api/v1/time-entries", json={
            "case_id": 21,
            "description": "Bad range",
            "start_time": "2026-06-15T11:00:00Z",
            "end_time": "2026-06-15T09:00:00Z",
            "billing_type": "professional_fee",
            "hourly_rate": "250.00",
        })
        assert invalid.status_code == 400
        assert "End time must be after start time" in invalid.json()["detail"]
    finally:
        cleanup(client)


def test_client_role_cannot_access_internal_time_entry_management():
    db = TimeEntryDBStub()
    client = build_client("client", db)
    try:
        res = client.get("/api/v1/time-entries")
        assert res.status_code == 403
    finally:
        cleanup(client)
