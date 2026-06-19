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


def invoice_obj(*, organization_id: int = 1, payments: list | None = None):
    now = datetime.now(timezone.utc)
    organization = SimpleNamespace(id=organization_id, name="Acme Legal", address=None, email=None, phone=None, tax_number=None)
    client = SimpleNamespace(id=10, name="Jordan Miles", email=None, phone=None, address=None, occupation=None, trn_no=None)
    case = SimpleNamespace(id=21, title="Matter 21")
    return SimpleNamespace(
        id=101,
        organization_id=organization_id,
        client_id=10,
        case_id=None,
        invoice_number="INV-2026-0001",
        currency="USD",
        status="sent",
        issue_date=date(2026, 6, 19),
        due_date=date(2026, 6, 29),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("15.00"),
        total=Decimal("115.00"),
        paid_amount=Decimal("0.00"),
        balance_due=Decimal("115.00"),
        notes=None,
        payment_instructions="Wire transfer",
        payment_account_id=None,
        payment_account=None,
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
        created_by=5,
        created_at=now,
        updated_at=now,
        organization=organization,
        client=client,
        case=case,
        line_items=[],
        payments=payments or [],
    )


class InvoiceVoidDBStub:
    def __init__(self, invoice):
        self.invoice = invoice
        self.added = []
        self.committed = False

    async def scalar(self, query, *args, **kwargs):
        q = str(query)
        params = query.compile().params
        if "FROM invoices" in q:
            if params.get("organization_id_1") != self.invoice.organization_id:
                return None
            return self.invoice
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True


def build_client(role: str, db: InvoiceVoidDBStub, org_id: int = 1):
    user = DummyUser(id=5, organization_id=org_id, name=f"{role} user", email="staff@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[InvoiceVoidDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_partner_can_void_unpaid_invoice_without_deleting_it():
    db = InvoiceVoidDBStub(invoice_obj())
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/invoices/101/void", json={"void_reason": "Duplicate draft"})
        assert res.status_code == 200
        body = res.json()
        assert body["display_status"] == "voided"
        assert body["void_reason"] == "Duplicate draft"
        assert db.invoice.status == "voided"
        assert db.invoice.voided_at is not None
        assert db.committed is True
    finally:
        cleanup(client)


def test_invoice_void_blocks_when_active_payments_exist():
    active_payment = SimpleNamespace(id=700, payment_source="direct", voided_at=None)
    db = InvoiceVoidDBStub(invoice_obj(payments=[active_payment]))
    client = build_client("admin", db)
    try:
        res = client.post("/api/v1/invoices/101/void", json={"void_reason": "Need reversal first"})
        assert res.status_code == 409
        assert "Void invoice payments first" in res.json()["detail"]
    finally:
        cleanup(client)


def test_invoice_void_is_org_scoped_and_role_protected():
    cross_org = InvoiceVoidDBStub(invoice_obj(organization_id=1))
    partner = build_client("partner", cross_org, org_id=2)
    try:
        res = partner.post("/api/v1/invoices/101/void", json={"void_reason": "Cross org"})
        assert res.status_code == 404
    finally:
        cleanup(partner)

    protected = InvoiceVoidDBStub(invoice_obj())
    client = build_client("lawyer", protected)
    try:
        res = client.post("/api/v1/invoices/101/void", json={"void_reason": "Not allowed"})
        assert res.status_code == 403
    finally:
        cleanup(client)
