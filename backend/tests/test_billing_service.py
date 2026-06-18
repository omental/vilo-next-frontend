from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.billing import (
    allocate_payment_across_line_items,
    get_effective_hourly_rate,
    resolve_invoice_payment_account,
    validate_billing_rate_payload,
)


class BillingServiceDB:
    def __init__(self, *, scalars=None):
        self.scalars = list(scalars or [])

    async def scalar(self, query, *args, **kwargs):
        if self.scalars:
            return self.scalars.pop(0)
        return None


@pytest.mark.asyncio
async def test_resolve_invoice_payment_account_uses_default_by_currency():
    account = SimpleNamespace(id=3, organization_id=9, currency="USD", is_default=True, is_active=True)
    db = BillingServiceDB(scalars=[account])

    resolved = await resolve_invoice_payment_account(
        db,
        organization_id=9,
        currency="USD",
        payment_account_id=None,
    )

    assert resolved.id == 3


@pytest.mark.asyncio
async def test_resolve_invoice_payment_account_blocks_cross_org_account():
    db = BillingServiceDB(scalars=[None])

    with pytest.raises(HTTPException) as exc:
        await resolve_invoice_payment_account(
            db,
            organization_id=9,
            currency="USD",
            payment_account_id=77,
        )

    assert exc.value.detail == "Payment account must belong to your organization"


@pytest.mark.asyncio
async def test_resolve_invoice_payment_account_blocks_currency_mismatch():
    account = SimpleNamespace(id=3, organization_id=9, currency="JMD", is_default=False, is_active=True)
    db = BillingServiceDB(scalars=[account])

    with pytest.raises(HTTPException) as exc:
        await resolve_invoice_payment_account(
            db,
            organization_id=9,
            currency="USD",
            payment_account_id=3,
        )

    assert exc.value.detail == "Payment account currency must match invoice currency"


@pytest.mark.asyncio
async def test_role_based_rate_applies_and_currency_specific_rates_work():
    user = SimpleNamespace(id=8, organization_id=5, role=SimpleNamespace(value="lawyer"))
    rate = SimpleNamespace(id=12, hourly_rate=Decimal("250.00"))
    db = BillingServiceDB(scalars=[user, None, rate])

    resolved = await get_effective_hourly_rate(db, 5, 8, "JMD")

    assert resolved.hourly_rate == Decimal("250.00")
    assert resolved.source == "role"


@pytest.mark.asyncio
async def test_user_override_beats_role_rate():
    user = SimpleNamespace(id=8, organization_id=5, role=SimpleNamespace(value="lawyer"))
    override = SimpleNamespace(id=19, hourly_rate=Decimal("325.00"))
    db = BillingServiceDB(scalars=[user, override])

    resolved = await get_effective_hourly_rate(db, 5, 8, "USD")

    assert resolved.hourly_rate == Decimal("325.00")
    assert resolved.source == "user_override"


@pytest.mark.asyncio
async def test_validate_billing_rate_payload_blocks_cross_org_user():
    db = BillingServiceDB(scalars=[None])

    with pytest.raises(HTTPException) as exc:
        await validate_billing_rate_payload(
            db,
            organization_id=5,
            rate_type="user_override",
            role_name=None,
            user_id=99,
        )

    assert exc.value.detail == "Staff user must belong to your organization"


def test_allocate_payment_across_line_items_is_proportional():
    invoice = SimpleNamespace(
        line_items=[
            SimpleNamespace(id=1, amount=Decimal("100.00")),
            SimpleNamespace(id=2, amount=Decimal("300.00")),
        ]
    )

    allocations = allocate_payment_across_line_items(invoice, Decimal("200.00"))

    assert allocations[0][1] == Decimal("50.00")
    assert allocations[1][1] == Decimal("150.00")
