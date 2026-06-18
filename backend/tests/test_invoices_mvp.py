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
            case_id=21,
            invoice_number="INV-2026-0001",
            currency="USD",
            status="draft",
            issue_date=date(2026, 6, 10),
            due_date=date(2026, 6, 20),
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("0.00"),
            paid_amount=Decimal("0.00"),
            balance_due=Decimal("0.00"),
            notes="Draft invoice",
            payment_instructions="Pay by bank transfer",
            payment_account_id=901,
            payment_account=SimpleNamespace(
                id=901,
                account_name="USD Operating",
                bank_name="National Bank",
                account_number="1234567890",
                currency="USD",
                swift_routing="NATBUS33",
                notes="Primary settlement account",
                payment_instructions="Wire to National Bank",
            ),
            created_by=1,
            created_at=now,
            updated_at=now,
            organization=org,
            client=client,
            case=SimpleNamespace(id=21, title="Matter 21"),
            line_items=[],
            payments=[],
        )
        other_client = SimpleNamespace(
            id=11,
            organization_id=1,
            name="Avery Stone",
            email="avery@example.com",
            phone="+15550001111",
            address="20 Main Street",
            occupation="Designer",
            trn_no="TRN-77",
        )
        other_invoice = SimpleNamespace(
            id=102,
            organization_id=1,
            client_id=11,
            case_id=22,
            invoice_number="INV-2026-0002",
            currency="USD",
            status="sent",
            issue_date=date(2026, 6, 11),
            due_date=date(2026, 6, 21),
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("0.00"),
            paid_amount=Decimal("0.00"),
            balance_due=Decimal("0.00"),
            notes="Second invoice",
            payment_instructions=None,
            payment_account_id=None,
            payment_account=None,
            created_by=1,
            created_at=now,
            updated_at=now,
            organization=org,
            client=other_client,
            case=SimpleNamespace(id=22, title="Matter 22"),
            line_items=[],
            payments=[],
        )
        self.invoice = invoice
        self.invoices = [invoice, other_invoice]
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
            rows = self.invoices
            params = query.compile().params
            requested_client_id = params.get("client_id_1")
            requested_case_id = params.get("case_id_1")
            if requested_client_id is not None:
                rows = [row for row in rows if row.client_id == requested_client_id]
            if requested_case_id is not None:
                rows = [row for row in rows if row.case_id == requested_case_id]
            return _Rows(rows)
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
        assert body["display_status"] == "draft"
        assert body["payment_method_summary"] == "Unpaid"
        assert body["matter_title"] == "Matter 21"
        assert body["payment_account"]["bank_name"] == "National Bank"
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


def test_list_invoices_can_filter_by_client_id():
    db = InvoiceDBStub()
    client = build_client("partner", db)
    try:
        res = client.get("/api/v1/invoices?client_id=10")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["client_id"] == 10
    finally:
        cleanup(client)


def test_list_invoices_can_filter_by_case_id():
    db = InvoiceDBStub()
    client = build_client("partner", db)
    try:
        res = client.get("/api/v1/invoices?case_id=22")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["case_id"] == 22
    finally:
        cleanup(client)
