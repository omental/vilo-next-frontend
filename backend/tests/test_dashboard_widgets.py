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


class DashboardDummyDB:
    def __init__(self, scalar_values: list, execute_rows: list[list]):
        self.scalar_values = list(scalar_values)
        self.execute_rows = list(execute_rows)

    async def scalar(self, query, *args, **kwargs):
        # Guardrail: dashboard widgets must stay org-scoped.
        assert "organization_id" in str(query)
        return self.scalar_values.pop(0)

    async def execute(self, query, *args, **kwargs):
        assert "organization_id" in str(query)

        class _Res:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Res(self.execute_rows.pop(0))


def _num(v):
    return float(v)


def test_dashboard_widgets_are_org_scoped_and_data_driven():
    user = DummyUser(id=11, organization_id=77, name="Partner", email="p@example.com", role=UserRole.partner)

    # Scalar call order is defined by the endpoint implementation.
    scalars = [
        12, 7, 2, 3, 4, 18, 1, 5, 6, 2, 9,  # case/today summary
        Decimal("1000.00"), Decimal("400.00"), Decimal("5000.00"),  # financial overview
        Decimal("600.00"), Decimal("300.00"), Decimal("70.00"), Decimal("40.00"),  # billing overview
    ]

    execute_rows = [
        [
            SimpleNamespace(id=1, title="Urgent filing", priority="high", due_date=datetime(2026, 5, 26, 10, 0, tzinfo=timezone.utc), case_id=101),
            SimpleNamespace(id=2, title="Draft response", priority="medium", due_date=datetime(2026, 5, 27, 10, 0, tzinfo=timezone.utc), case_id=102),
        ],
        [
            SimpleNamespace(id=8, title="Court hearing", event_type="court", start_at=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc), case_id=101),
        ],
        [
            SimpleNamespace(month=datetime(2026, 3, 1, tzinfo=timezone.utc), amount=Decimal("800.00")),
            SimpleNamespace(month=datetime(2026, 4, 1, tzinfo=timezone.utc), amount=Decimal("900.00")),
        ],
        [
            SimpleNamespace(id=101, title="Apex merger", status="active", name="Apex Group", lead_name="Sarah J.", next_due=datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)),
        ],
    ]

    db = DashboardDummyDB(scalars, execute_rows)

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[DashboardDummyDB]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db

    try:
        client = TestClient(app)
        res = client.get("/api/v1/reports/dashboard/widgets")
        assert res.status_code == 200
        body = res.json()

        # Financial guardrail: trust deposits are not invoice revenue.
        assert _num(body["financial_overview"]["monthly_revenue"]) == 1000.0
        assert _num(body["financial_overview"]["trust_account_balance"]) == 5000.0
        assert _num(body["financial_overview"]["net_profit"]) == 600.0

        # Billing rollup shape and values.
        assert _num(body["billing_overview"]["paid_total"]) == 600.0
        assert _num(body["billing_overview"]["unpaid_total"]) == 300.0
        assert _num(body["billing_overview"]["draft_total"]) == 70.0
        assert _num(body["billing_overview"]["overdue_total"]) == 40.0

        # Active cases payload contains client + lead + due_date fields.
        assert body["active_cases"][0]["client_name"] == "Apex Group"
        assert body["active_cases"][0]["lead"] == "Sarah J."
        assert body["active_cases"][0]["display_number"] == "C-101"
    finally:
        app.dependency_overrides.clear()


def test_dashboard_widgets_forbidden_for_client_role():
    user = DummyUser(id=21, organization_id=88, name="Client", email="c@example.com", role=UserRole.client)

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[DashboardDummyDB]:
        yield DashboardDummyDB([], [])

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db

    try:
        client = TestClient(app)
        res = client.get("/api/v1/reports/dashboard/widgets")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_dashboard_widgets_paralegal_gets_assignment_scoped_non_financial_dashboard():
    user = DummyUser(id=31, organization_id=77, name="Para", email="para@example.com", role=UserRole.paralegal)
    scalars = [3, 2, 1, 0, 1, 5, 0, 1, 2, 1, 4]
    execute_rows = [
        [
            SimpleNamespace(id=90, title="File affidavit", priority="high", due_date=datetime(2026, 5, 26, 10, 0, tzinfo=timezone.utc), case_id=101),
        ],
        [
            SimpleNamespace(id=12, title="Assigned case hearing", event_type="court", start_at=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc), case_id=101),
        ],
        [
            SimpleNamespace(id=101, title="Assigned matter", status="active", name="Scoped Client", lead_name="Partner", next_due=datetime(2026, 5, 28, 10, 0, tzinfo=timezone.utc)),
        ],
    ]
    db = DashboardDummyDB(scalars, execute_rows)

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[DashboardDummyDB]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db

    try:
        client = TestClient(app)
        res = client.get("/api/v1/reports/dashboard/widgets")
        assert res.status_code == 200
        body = res.json()
        assert body["firm_snapshot"]["total_cases"] == 3
        assert body["today_overview"]["priority_timeline"][0]["title"] == "File affidavit"
        assert body["active_cases"][0]["client_name"] == "Scoped Client"
        assert body["financial_overview"] is None
        assert body["billing_overview"] is None
    finally:
        app.dependency_overrides.clear()
