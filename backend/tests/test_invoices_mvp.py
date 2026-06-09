from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.main import app
from app.models.enums import RecordStatus, UserRole
from app.services.pdf import build_firm_details


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


class InvoiceDBStub:
    def __init__(self):
        now = datetime.now(timezone.utc)
        org = SimpleNamespace(id=1, name="Acme Legal", address=None, email=None, phone=None, tax_number=None)
        client = SimpleNamespace(
            id=10,
            organization_id=1,
            name="Jordan Miles",
            email="jordan@example.com",
            phone="+15551230000",
            address="12 Court Street",
            occupation="Architect",
            trn_no="TRN-22",
        )
        invoice = SimpleNamespace(
            id=101,
            organization_id=1,
            client_id=10,
            case_id=None,
            invoice_number="INV-2026-0001",
            status="draft",
            issue_date=date(2026, 6, 10),
            due_date=date(2026, 6, 20),
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("0.00"),
            paid_amount=Decimal("0.00"),
            balance_due=Decimal("0.00"),
            notes="Draft invoice",
            created_by=1,
            created_at=now,
            updated_at=now,
            organization=org,
            client=client,
            line_items=[],
        )
        self.invoice = invoice
        self.scalar_queue = []

    async def scalar(self, query, *args, **kwargs):
        q = str(query)
        assert "organization_id" in q
        if self.scalar_queue:
            return self.scalar_queue.pop(0)
        if "FROM invoices" in q:
            return self.invoice
        return None

    async def scalars(self, query, *args, **kwargs):
        q = str(query)
        assert "organization_id" in q

        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        if "FROM invoices" in q:
            return _Rows([self.invoice])
        return _Rows([])


def build_client(role: str, db: InvoiceDBStub, org_id: int = 1):
    user = DummyUser(id=5, organization_id=org_id, name=f"{role} user", email="staff@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[InvoiceDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_invoice_detail_includes_safe_firm_and_client_details():
    db = InvoiceDBStub()
    client = build_client("partner", db)
    try:
        res = client.get("/api/v1/invoices/101")
        assert res.status_code == 200
        body = res.json()
        assert body["organization"] == {
            "id": 1,
            "name": "Acme Legal",
            "address": None,
            "email": None,
            "phone": None,
            "tax_number": None,
        }
        assert body["client"]["name"] == "Jordan Miles"
        assert body["client"]["occupation"] == "Architect"
        assert "slug" not in body["organization"]
    finally:
        cleanup(client)


def test_invoice_detail_cross_org_access_remains_hidden():
    db = InvoiceDBStub()
    db.scalar_queue = [None]
    client = build_client("partner", db, org_id=1)
    try:
        res = client.get("/api/v1/invoices/999")
        assert res.status_code == 404
    finally:
        cleanup(client)


def test_build_firm_details_uses_safe_fallbacks_only():
    details = build_firm_details(SimpleNamespace(name="Acme Legal", slug="acme-legal"))
    assert details == ["Acme Legal"]
