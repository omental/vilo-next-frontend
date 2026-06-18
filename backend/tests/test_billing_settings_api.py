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


class SettingsDBStub:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.payment_accounts = [
            SimpleNamespace(
                id=1,
                organization_id=1,
                account_name="USD Main",
                bank_name="Bank A",
                account_number="1111",
                currency="USD",
                swift_routing=None,
                notes=None,
                payment_instructions="Wire transfer",
                is_default=True,
                is_active=True,
                created_by_id=5,
                created_at=now,
                updated_at=now,
            )
        ]
        self.billing_rates = []
        self.staff_user = SimpleNamespace(id=7, organization_id=1, role=SimpleNamespace(value="lawyer"))
        self.refreshed = []

    async def scalar(self, query, *args, **kwargs):
        q = str(query)
        params = query.compile().params
        if "FROM firm_payment_accounts" in q:
            account_id = params.get("id_1")
            if account_id is not None:
                return next((row for row in self.payment_accounts if row.id == account_id), None)
            currency = params.get("currency_1")
            return next((row for row in self.payment_accounts if row.currency == currency and row.is_default and row.is_active), None)
        if "FROM users" in q:
            return self.staff_user
        if "FROM billing_rates" in q:
            rate_id = params.get("id_1")
            if rate_id is not None:
                return next((row for row in self.billing_rates if row.id == rate_id), None)
            if params.get("rate_type_1") == "user_override":
                return next((row for row in self.billing_rates if row.rate_type == "user_override"), None)
            return next((row for row in self.billing_rates if row.rate_type == "role"), None)
        return None

    async def scalars(self, query, *args, **kwargs):
        q = str(query)

        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        if "FROM firm_payment_accounts" in q:
            return _Rows(self.payment_accounts)
        if "FROM billing_rates" in q:
            return _Rows(self.billing_rates)
        return _Rows([])

    def add(self, obj):
        if obj.__class__.__name__ == "FirmPaymentAccount":
            obj.id = len(self.payment_accounts) + 1
            self.payment_accounts.append(obj)
        elif obj.__class__.__name__ == "BillingRate":
            obj.id = len(self.billing_rates) + 1
            self.billing_rates.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        self.refreshed.append(obj)


def build_client(role: str, db: SettingsDBStub):
    user = DummyUser(id=5, organization_id=1, name=role, email="user@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[SettingsDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_partner_can_create_payment_account_and_default_flips():
    db = SettingsDBStub()
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/settings/payment-accounts", json={
            "account_name": "USD Reserve",
            "bank_name": "Bank B",
            "account_number": "2222",
            "currency": "USD",
            "is_default": True,
        })
        assert res.status_code == 200
        body = res.json()
        assert body["account_name"] == "USD Reserve"
        assert body["is_default"] is True
        assert db.payment_accounts[0].is_default is False
    finally:
        cleanup(client)


def test_client_blocked_from_billing_rate_management():
    db = SettingsDBStub()
    client = build_client("client", db)
    try:
        res = client.post("/api/v1/settings/billing-rates", json={
            "rate_type": "role",
            "role_name": "lawyer",
            "currency": "USD",
            "hourly_rate": "250.00",
        })
        assert res.status_code == 403
    finally:
        cleanup(client)


def test_effective_rate_endpoint_returns_user_override():
    db = SettingsDBStub()
    now = datetime.now(timezone.utc)
    db.billing_rates = [
        SimpleNamespace(
            id=1,
            organization_id=1,
            rate_type="role",
            role_name="lawyer",
            user_id=None,
            currency="USD",
            hourly_rate=Decimal("200.00"),
            is_active=True,
            created_by_id=5,
            created_at=now,
            updated_at=now,
        ),
        SimpleNamespace(
            id=2,
            organization_id=1,
            rate_type="user_override",
            role_name=None,
            user_id=7,
            currency="USD",
            hourly_rate=Decimal("325.00"),
            is_active=True,
            created_by_id=5,
            created_at=now,
            updated_at=now,
        ),
    ]
    client = build_client("lawyer", db)
    try:
        res = client.get("/api/v1/settings/billing-rates/effective?user_id=7&currency=USD")
        assert res.status_code == 200
        body = res.json()
        assert body["hourly_rate"] == "325.00"
        assert body["source"] == "user_override"
    finally:
        cleanup(client)
