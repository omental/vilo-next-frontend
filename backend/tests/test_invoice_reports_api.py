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


class ReportsDBStub:
    def __init__(self):
        active_direct = SimpleNamespace(payment_source="direct", voided_at=None)
        active_trust = SimpleNamespace(payment_source="trust", voided_at=None)
        voided_direct = SimpleNamespace(payment_source="direct", voided_at=datetime.now(timezone.utc))
        self.invoices = [
            SimpleNamespace(
                id=1,
                organization_id=1,
                client_id=10,
                case_id=20,
                invoice_number="INV-1",
                currency="USD",
                status="paid",
                issue_date=date(2026, 6, 10),
                due_date=date(2026, 6, 15),
                subtotal=Decimal("100.00"),
                tax_amount=Decimal("15.00"),
                total=Decimal("115.00"),
                paid_amount=Decimal("115.00"),
                balance_due=Decimal("0.00"),
                created_by=7,
                client=SimpleNamespace(name="Client A"),
                case=SimpleNamespace(title="Matter A"),
                payments=[active_direct],
                created_at=datetime.now(timezone.utc),
            ),
            SimpleNamespace(
                id=2,
                organization_id=1,
                client_id=11,
                case_id=21,
                invoice_number="INV-2",
                currency="USD",
                status="sent",
                issue_date=date(2026, 6, 11),
                due_date=date(2026, 6, 12),
                subtotal=Decimal("100.00"),
                tax_amount=Decimal("15.00"),
                total=Decimal("115.00"),
                paid_amount=Decimal("50.00"),
                balance_due=Decimal("65.00"),
                created_by=8,
                client=SimpleNamespace(name="Client B"),
                case=SimpleNamespace(title="Matter B"),
                payments=[active_trust],
                created_at=datetime.now(timezone.utc),
            ),
            SimpleNamespace(
                id=3,
                organization_id=1,
                client_id=12,
                case_id=22,
                invoice_number="INV-3",
                currency="USD",
                status="sent",
                issue_date=date(2026, 6, 1),
                due_date=date(2026, 6, 5),
                subtotal=Decimal("100.00"),
                tax_amount=Decimal("15.00"),
                total=Decimal("115.00"),
                paid_amount=Decimal("0.00"),
                balance_due=Decimal("115.00"),
                created_by=8,
                client=SimpleNamespace(name="Client C"),
                case=SimpleNamespace(title="Matter C"),
                payments=[voided_direct],
                created_at=datetime.now(timezone.utc),
            ),
            SimpleNamespace(
                id=4,
                organization_id=1,
                client_id=13,
                case_id=23,
                invoice_number="INV-4",
                currency="USD",
                status="partially_paid",
                issue_date=date(2026, 6, 9),
                due_date=date(2026, 6, 30),
                subtotal=Decimal("100.00"),
                tax_amount=Decimal("15.00"),
                total=Decimal("115.00"),
                paid_amount=Decimal("100.00"),
                balance_due=Decimal("15.00"),
                created_by=9,
                client=SimpleNamespace(name="Client D"),
                case=SimpleNamespace(title="Matter D"),
                payments=[active_direct, active_trust],
                created_at=datetime.now(timezone.utc),
            ),
        ]
        self.execute_rows = [
            [SimpleNamespace(period=datetime(2026, 6, 1), currency="USD", amount=Decimal("265.00"))],
            [SimpleNamespace(client_id=10, client_name="Client A", currency="USD", amount=Decimal("115.00"))],
            [SimpleNamespace(case_id=20, matter_title="Matter A", currency="USD", amount=Decimal("115.00"))],
            [SimpleNamespace(staff_id=7, staff_name="Lawyer A", currency="USD", amount=Decimal("115.00"))],
            [SimpleNamespace(currency="USD", amount=Decimal("30.00"))],
        ]

    async def scalars(self, query, *args, **kwargs):
        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Rows(self.invoices)

    async def execute(self, query, *args, **kwargs):
        class _Res:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Res(self.execute_rows.pop(0))


def build_client(db: ReportsDBStub):
    user = DummyUser(id=5, organization_id=1, name="partner", email="partner@example.com", role=UserRole.partner)

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[ReportsDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_invoice_reports_endpoint_separates_status_and_payment_methods():
    db = ReportsDBStub()
    client = build_client(db)
    try:
        res = client.get("/api/v1/reports/invoices")
        assert res.status_code == 200
        body = res.json()
        assert len(body["paid_invoices"]) == 1
        assert len(body["overdue_invoices"]) == 2
        assert body["payment_method_report"]["counts"]["Direct Payment"] == 1
        assert body["payment_method_report"]["counts"]["Trust Applied"] == 1
        assert body["payment_method_report"]["counts"]["Mixed"] == 1
        assert body["payment_method_report"]["counts"]["Voided/Reversed"] == 1
        assert body["revenue_by_client"][0]["amount"] == 115.0
        assert body["gct_tax_report"][0]["amount"] == 30.0
    finally:
        cleanup(client)
