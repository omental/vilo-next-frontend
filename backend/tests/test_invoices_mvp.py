from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.main import app
from app.models.invoice import Invoice
from app.models.enums import RecordStatus, UserRole
from app.services.pdf import build_firm_details, resolve_invoice_recipient_name


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


class InvoiceCreateDBStub:
    def __init__(self, *, allow_client=True, case_client_id=10, account_currency="JMD"):
        self.allow_client = allow_client
        self.case_client_id = case_client_id
        self.invoice = None
        self.added = []
        self.org = SimpleNamespace(
            id=1,
            name="Acme Legal",
            address="1 Firm Street",
            email="billing@acme.test",
            phone="555-0100",
            tax_number="TRN-FIRM",
            invoice_tax_rate=Decimal("15.00"),
        )
        self.client = SimpleNamespace(
            id=10,
            organization_id=1,
            name="Jordan Miles",
            email="jordan@example.com",
            phone="+15551230000",
            address="12 Court Street",
            occupation="Architect",
            trn_no="TRN-22",
        )
        self.case = SimpleNamespace(id=21, organization_id=1, client_id=case_client_id, title="Matter 21")
        self.account = SimpleNamespace(
            id=901,
            organization_id=1,
            account_name="JMD Operating",
            bank_name="National Bank",
            account_number="1234567890",
            currency=account_currency,
            swift_routing=None,
            notes=None,
            payment_instructions="Pay by bank transfer",
            is_default=True,
            is_active=True,
        )

    async def scalar(self, query, *args, **kwargs):
        q = str(query)
        if "count(invoices.id)" in q:
            return 0
        if q.startswith("SELECT invoices.id \nFROM invoices"):
            return None
        if "FROM clients" in q:
            return self.client if self.allow_client else None
        if "FROM cases" in q:
            return self.case
        if "FROM organizations" in q:
            return self.org
        if "FROM firm_payment_accounts" in q:
            return self.account
        if "FROM invoices" in q:
            self._prepare_invoice()
            return self.invoice
        return None

    async def scalars(self, query, *args, **kwargs):
        q = str(query)

        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        if "FROM invoices" in q:
            self._prepare_invoice()
            return _Rows([self.invoice] if self.invoice else [])
        return _Rows([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Invoice):
            self.invoice = obj

    async def flush(self):
        if self.invoice and self.invoice.id is None:
            self.invoice.id = 501
        if self.invoice:
            for index, line in enumerate(self.invoice.line_items, start=1):
                if line.id is None:
                    line.id = 700 + index

    async def commit(self):
        await self.flush()

    async def rollback(self):
        return None

    def _prepare_invoice(self):
        if not self.invoice:
            return
        self.invoice.__dict__["organization"] = self.org
        self.invoice.__dict__["client"] = self.client if self.invoice.client_id else None
        self.invoice.__dict__["case"] = self.case if self.invoice.case_id else None
        self.invoice.__dict__["payment_account"] = self.account
        self.invoice.__dict__["payments"] = []


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
        assert body["payment_method_summary"] == "Not Paid"
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


def test_invoice_pdf_recipient_name_resolves_manual_and_existing_clients():
    invoice = SimpleNamespace(manual_client_name="Walk-in Recipient")
    assert resolve_invoice_recipient_name(invoice, None) == "Walk-in Recipient"
    assert resolve_invoice_recipient_name(invoice, SimpleNamespace(name="Jordan Miles")) == "Jordan Miles"


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


def _valid_invoice_payload(**overrides):
    payload = {
        "client_id": 10,
        "issue_date": "2026-07-24",
        "currency": "JMD",
        "line_items": [
            {
                "line_type": "legal_fee",
                "description": "Legal advice",
                "quantity": 2,
                "unit_price": 5000,
                "amount": 10000,
            }
        ],
        "subtotal": 10000,
        "tax_amount": 1500,
        "total": 11500,
    }
    payload.update(overrides)
    return payload


def test_valid_existing_client_invoice_creates_and_is_visible_in_list():
    db = InvoiceCreateDBStub()
    client = build_client("partner", db)
    try:
        created = client.post("/api/v1/invoices", json=_valid_invoice_payload(payment_account_id=901))
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["id"] == 501
        assert body["client"]["name"] == "Jordan Miles"
        assert body["currency"] == "JMD"
        assert body["subtotal"] == "10000.00"
        assert body["tax_amount"] == "1500.00"
        assert body["total"] == "11500.00"
        assert body["payment_account_id"] == 901
        assert body["can_apply_trust"] is False

        listed = client.get("/api/v1/invoices")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [501]
    finally:
        cleanup(client)


def test_valid_manual_client_invoice_without_case_creates_and_serializes():
    db = InvoiceCreateDBStub()
    client = build_client("admin", db)
    try:
        payload = _valid_invoice_payload(client_id=None, manual_client_name="Walk-in Recipient")
        created = client.post("/api/v1/invoices", json=payload)
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["client_id"] is None
        assert body["client"] is None
        assert body["manual_client_name"] == "Walk-in Recipient"
        assert body["case_id"] is None
    finally:
        cleanup(client)


def test_selected_case_and_client_ids_are_accepted_when_relationship_matches(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    from app.api.v1 import invoices as invoices_module

    monkeypatch.setattr(invoices_module, "create_case_timeline_event", _noop)
    db = InvoiceCreateDBStub()
    client = build_client("partner", db)
    try:
        created = client.post("/api/v1/invoices", json=_valid_invoice_payload(case_id=21, payment_account_id=901))
        assert created.status_code == 200, created.text
        assert created.json()["client_id"] == 10
        assert created.json()["case_id"] == 21
        assert created.json()["payment_account_id"] == 901
    finally:
        cleanup(client)


def test_invoice_rejects_neither_or_both_recipient_modes():
    db = InvoiceCreateDBStub()
    client = build_client("partner", db)
    try:
        neither = client.post(
            "/api/v1/invoices",
            json=_valid_invoice_payload(client_id=None, manual_client_name=None),
        )
        assert neither.status_code == 422
        assert neither.json()["errors"][0]["field"] == "client_id"

        both = client.post(
            "/api/v1/invoices",
            json=_valid_invoice_payload(client_id=10, manual_client_name="Walk-in Recipient"),
        )
        assert both.status_code == 422
        assert both.json()["errors"][0]["field"] == "client_id"
    finally:
        cleanup(client)


def test_invoice_validation_returns_exact_missing_and_invalid_field_errors():
    db = InvoiceCreateDBStub()
    client = build_client("partner", db)
    try:
        missing = client.post("/api/v1/invoices", json={"client_id": 10})
        assert missing.status_code == 422
        missing_body = missing.json()
        assert missing_body["detail"] == "Invoice validation failed"
        assert {"field": "issue_date", "message": "This field is required."} in missing_body["errors"]
        assert {"field": "line_items", "message": "This field is required."} in missing_body["errors"]

        invalid = client.post(
            "/api/v1/invoices",
            json=_valid_invoice_payload(line_items=[{"line_type": "legal_fee", "description": "Advice", "quantity": 1, "unit_price": 0}]),
        )
        assert invalid.status_code == 422
        assert any(error["field"] == "line_items.0.unit_price" for error in invalid.json()["errors"])
    finally:
        cleanup(client)


def test_invoice_rejects_cross_tenant_client_and_case_client_mismatch():
    cross_tenant_db = InvoiceCreateDBStub(allow_client=False)
    client = build_client("partner", cross_tenant_db)
    try:
        response = client.post("/api/v1/invoices", json=_valid_invoice_payload())
        assert response.status_code == 400
        assert response.json()["errors"] == [
            {"field": "client_id", "message": "The selected client is invalid or unavailable."}
        ]
    finally:
        cleanup(client)

    mismatch_db = InvoiceCreateDBStub(case_client_id=999)
    client = build_client("partner", mismatch_db)
    try:
        response = client.post("/api/v1/invoices", json=_valid_invoice_payload(case_id=21))
        assert response.status_code == 400
        assert response.json()["errors"][0]["field"] == "case_id"
    finally:
        cleanup(client)


def test_invoice_rejects_currency_account_and_total_mismatches():
    wrong_currency_db = InvoiceCreateDBStub(account_currency="USD")
    client = build_client("partner", wrong_currency_db)
    try:
        response = client.post("/api/v1/invoices", json=_valid_invoice_payload(payment_account_id=901))
        assert response.status_code == 400
        assert response.json()["errors"][0]["field"] == "currency"
    finally:
        cleanup(client)

    totals_db = InvoiceCreateDBStub()
    client = build_client("partner", totals_db)
    try:
        response = client.post("/api/v1/invoices", json=_valid_invoice_payload(total=999))
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "total"
    finally:
        cleanup(client)
