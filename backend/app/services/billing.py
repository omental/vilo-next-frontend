from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing_rate import BillingRate
from app.models.case import Case
from app.models.firm_payment_account import FirmPaymentAccount
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.invoice_payment import InvoicePayment
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.services.finance import money, normalize_currency

ZERO = Decimal("0.00")
MANAGE_ROLES = {"partner", "admin"}
VIEW_ROLES = {"partner", "admin", "lawyer", "paralegal"}


@dataclass
class EffectiveRate:
    hourly_rate: Decimal
    source: str
    rate_id: int | None = None


async def clear_default_payment_accounts(
    db: AsyncSession,
    *,
    organization_id: int,
    currency: str,
    exclude_account_id: int | None = None,
) -> None:
    rows = (
        await db.scalars(
            select(FirmPaymentAccount).where(
                FirmPaymentAccount.organization_id == organization_id,
                FirmPaymentAccount.currency == currency,
                FirmPaymentAccount.is_default == True,
                FirmPaymentAccount.is_active == True,
            )
        )
    ).all()
    for row in rows:
        if exclude_account_id is not None and row.id == exclude_account_id:
            continue
        row.is_default = False


async def resolve_invoice_payment_account(
    db: AsyncSession,
    *,
    organization_id: int,
    currency: str,
    payment_account_id: int | None,
) -> FirmPaymentAccount:
    normalized_currency = normalize_currency(currency)
    account = None
    if payment_account_id is not None:
        account = await db.scalar(
            select(FirmPaymentAccount).where(
                FirmPaymentAccount.id == payment_account_id,
                FirmPaymentAccount.organization_id == organization_id,
            )
        )
        if not account:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment account must belong to your organization")
    else:
        account = await db.scalar(
            select(FirmPaymentAccount).where(
                FirmPaymentAccount.organization_id == organization_id,
                FirmPaymentAccount.currency == normalized_currency,
                FirmPaymentAccount.is_default == True,
                FirmPaymentAccount.is_active == True,
            )
        )
        if not account:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment account is required for this invoice currency")
    if account.currency != normalized_currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment account currency must match invoice currency")
    return account


async def get_effective_hourly_rate(
    db: AsyncSession,
    organization_id: int,
    user_id: int,
    currency: str,
) -> EffectiveRate:
    normalized_currency = normalize_currency(currency)
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == organization_id))
    if not user or user.role.value == "client":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Staff user must belong to your organization")

    user_override = await db.scalar(
        select(BillingRate).where(
            BillingRate.organization_id == organization_id,
            BillingRate.rate_type == "user_override",
            BillingRate.user_id == user_id,
            BillingRate.currency == normalized_currency,
            BillingRate.is_active == True,
        )
    )
    if user_override:
        return EffectiveRate(hourly_rate=money(user_override.hourly_rate), source="user_override", rate_id=user_override.id)

    role_rate = await db.scalar(
        select(BillingRate).where(
            BillingRate.organization_id == organization_id,
            BillingRate.rate_type == "role",
            BillingRate.role_name == user.role.value,
            BillingRate.currency == normalized_currency,
            BillingRate.is_active == True,
        )
    )
    if role_rate:
        return EffectiveRate(hourly_rate=money(role_rate.hourly_rate), source="role", rate_id=role_rate.id)

    return EffectiveRate(hourly_rate=ZERO, source="default", rate_id=None)


async def validate_billing_rate_payload(
    db: AsyncSession,
    *,
    organization_id: int,
    rate_type: str,
    role_name: str | None,
    user_id: int | None,
) -> tuple[str | None, int | None]:
    normalized_type = (rate_type or "").strip().lower()
    if normalized_type not in {"role", "user_override"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid rate type")

    if normalized_type == "role":
        normalized_role = (role_name or "").strip().lower()
        if normalized_role not in VIEW_ROLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role name")
        return normalized_role, None

    if user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User override requires user_id")
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == organization_id))
    if not user or user.role.value == "client":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Staff user must belong to your organization")
    return None, user_id


def allocate_payment_across_line_items(invoice: Invoice, payment_amount: Decimal) -> list[tuple[InvoiceLineItem, Decimal]]:
    payment_amount = money(payment_amount)
    lines = list(getattr(invoice, "line_items", []) or [])
    if payment_amount <= ZERO or not lines:
        return []

    total_amount = sum((money(line.amount) for line in lines), ZERO)
    if total_amount <= ZERO:
        return []

    allocations: list[tuple[InvoiceLineItem, Decimal]] = []
    running_total = ZERO
    for index, line in enumerate(lines):
        line_amount = money(line.amount)
        if index == len(lines) - 1:
            allocated = money(payment_amount - running_total)
        else:
            allocated = money((payment_amount * line_amount) / total_amount)
            running_total += allocated
        allocations.append((line, allocated))
    return allocations


async def build_revenue_by_staff_report(
    db: AsyncSession,
    *,
    organization_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    staff_user_id: int | None = None,
    currency: str | None = None,
) -> list[dict]:
    payment_filters = [InvoicePayment.organization_id == organization_id, InvoicePayment.voided_at.is_(None)]
    if date_from is not None:
        payment_filters.append(InvoicePayment.paid_at >= date_from)
    if date_to is not None:
        payment_filters.append(InvoicePayment.paid_at <= date_to)
    if currency is not None:
        payment_filters.append(InvoicePayment.currency == normalize_currency(currency))

    invoices = (
        await db.scalars(
            select(Invoice)
            .join(InvoicePayment, InvoicePayment.invoice_id == Invoice.id)
            .where(and_(*payment_filters))
            .options(
                selectinload(Invoice.line_items).selectinload(InvoiceLineItem.time_entry),
                selectinload(Invoice.line_items).selectinload(InvoiceLineItem.staff_user),
                selectinload(Invoice.payments),
                selectinload(Invoice.creator),
            )
        )
    ).all()

    rollup: dict[tuple[int, str], dict] = {}
    for invoice in invoices:
        active_payments = [
            payment for payment in getattr(invoice, "payments", [])
            if getattr(payment, "voided_at", None) is None
            and payment.organization_id == organization_id
            and (date_from is None or payment.paid_at >= date_from)
            and (date_to is None or payment.paid_at <= date_to)
            and (currency is None or payment.currency == normalize_currency(currency))
        ]
        if not active_payments:
            continue

        per_staff_billed = defaultdict(lambda: ZERO)
        per_staff_collected = defaultdict(lambda: ZERO)
        per_staff_direct = defaultdict(lambda: ZERO)
        per_staff_trust = defaultdict(lambda: ZERO)

        for line in getattr(invoice, "line_items", []) or []:
            staff_id = getattr(getattr(line, "time_entry", None), "user_id", None) or getattr(line, "staff_user_id", None)
            if staff_id is None:
                staff_id = getattr(invoice, "created_by", None)
            if staff_user_id is not None and staff_id != staff_user_id:
                continue
            line_amount = money(getattr(line, "amount", ZERO))
            per_staff_billed[staff_id] += line_amount
            staff_name = (
                getattr(getattr(getattr(line, "time_entry", None), "user", None), "name", None)
                or getattr(getattr(line, "staff_user", None), "name", None)
                or getattr(getattr(invoice, "creator", None), "name", None)
                or f"Staff #{staff_id}"
            )

            for payment in active_payments:
                for allocated_line, allocated_amount in allocate_payment_across_line_items(invoice, payment.amount):
                    if allocated_line.id != line.id:
                        continue
                    per_staff_collected[staff_id] += allocated_amount
                    if payment.payment_source == "trust":
                        per_staff_trust[staff_id] += allocated_amount
                    else:
                        per_staff_direct[staff_id] += allocated_amount

            key = (staff_id, invoice.currency)
            row = rollup.setdefault(
                key,
                {
                    "staff_user_id": staff_id,
                    "staff_name": staff_name,
                    "currency": invoice.currency,
                    "total_billed": ZERO,
                    "total_collected": ZERO,
                    "invoice_ids": set(),
                    "direct_collected": ZERO,
                    "trust_collected": ZERO,
                },
            )
            row["invoice_ids"].add(invoice.id)

        for staff_id, billed_amount in per_staff_billed.items():
            key = (staff_id, invoice.currency)
            row = rollup[key]
            row["total_billed"] += billed_amount
            row["total_collected"] += per_staff_collected[staff_id]
            row["direct_collected"] += per_staff_direct[staff_id]
            row["trust_collected"] += per_staff_trust[staff_id]

    rows = []
    for row in rollup.values():
        rows.append(
            {
                "staff_user_id": row["staff_user_id"],
                "staff_name": row["staff_name"],
                "currency": row["currency"],
                "total_billed": money(row["total_billed"]),
                "total_collected": money(row["total_collected"]),
                "invoice_count": len(row["invoice_ids"]),
                "direct_collected": money(row["direct_collected"]),
                "trust_collected": money(row["trust_collected"]),
            }
        )
    rows.sort(key=lambda item: (item["staff_name"], item["currency"]))
    return rows


async def build_time_by_staff_report(
    db: AsyncSession,
    *,
    organization_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    staff_user_id: int | None = None,
    currency: str | None = None,
) -> list[dict]:
    filters = [TimeEntry.organization_id == organization_id, TimeEntry.status.in_(["billable", "invoiced"])]
    time_anchor = func.date(func.coalesce(TimeEntry.start_time, TimeEntry.created_at))
    if date_from is not None:
        filters.append(time_anchor >= date_from)
    if date_to is not None:
        filters.append(time_anchor <= date_to)
    if staff_user_id is not None:
        filters.append(TimeEntry.user_id == staff_user_id)
    if currency is not None:
        filters.append(TimeEntry.currency == normalize_currency(currency))

    rows = (
        await db.execute(
            select(
                TimeEntry.user_id.label("staff_user_id"),
                User.name.label("staff_name"),
                TimeEntry.currency.label("currency"),
                func.coalesce(func.sum(TimeEntry.duration_minutes), 0).label("duration_minutes"),
                func.coalesce(func.sum(TimeEntry.amount), 0).label("estimated_value"),
            )
            .join(User, User.id == TimeEntry.user_id)
            .where(and_(*filters))
            .group_by(TimeEntry.user_id, User.name, TimeEntry.currency)
            .order_by(User.name.asc(), TimeEntry.currency.asc())
        )
    ).all()

    return [
        {
            "staff_user_id": row.staff_user_id,
            "staff_name": row.staff_name,
            "currency": row.currency,
            "total_hours": money(Decimal(str(row.duration_minutes or 0)) / Decimal("60")),
            "billable_hours": money(Decimal(str(row.duration_minutes or 0)) / Decimal("60")),
            "estimated_value": money(row.estimated_value),
        }
        for row in rows
    ]


async def validate_time_entry_invoice_link(
    db: AsyncSession,
    *,
    organization_id: int,
    invoice: Invoice,
    time_entry_id: int,
) -> TimeEntry:
    time_entry = await db.scalar(
        select(TimeEntry)
        .where(TimeEntry.id == time_entry_id, TimeEntry.organization_id == organization_id)
        .options(selectinload(TimeEntry.user), selectinload(TimeEntry.case))
    )
    if not time_entry:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Time entry must belong to your organization")
    if time_entry.case_id and invoice.case_id and time_entry.case_id != invoice.case_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Time entry does not belong to invoice matter")
    if time_entry.client_id and time_entry.client_id != invoice.client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Time entry does not belong to invoice client")
    if time_entry.currency != invoice.currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Time entry currency must match invoice currency")
    if time_entry.billing_type in {"non_billable", "no_charge"} or time_entry.status == "non_billable":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Non-billable time entries cannot be invoiced")
    if time_entry.invoice_id and time_entry.invoice_id != invoice.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Time entry already linked to another invoice")
    return time_entry


async def validate_case_client_alignment(
    db: AsyncSession,
    *,
    organization_id: int,
    case_id: int | None,
    client_id: int | None,
) -> tuple[int | None, int | None]:
    if case_id is None:
        return None, client_id
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == organization_id))
    if not case:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case must belong to your organization")
    if client_id is not None and case.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case does not belong to client")
    return case.id, case.client_id
