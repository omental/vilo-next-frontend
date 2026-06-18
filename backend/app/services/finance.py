from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.client import Client
from app.models.expense import Expense
from app.models.invoice import Invoice
from app.models.invoice_payment import InvoicePayment
from app.models.operating_account import OperatingAccount
from app.models.operating_transaction import OperatingTransaction
from app.models.trust_account import TrustAccount
from app.models.trust_ledger import TrustLedger
from app.models.trust_receipt import TrustReceipt
from app.models.trust_transaction import TrustTransaction
from app.services.audit import log_audit_event

ZERO = Decimal("0.00")
TRUST_INFLOW_TYPES = {"deposit"}
TRUST_OUTFLOW_TYPES = {"disbursement", "refund", "transfer_to_operating"}
TRUST_ALL_TYPES = TRUST_INFLOW_TYPES | TRUST_OUTFLOW_TYPES | {"adjustment"}
OPERATING_REVENUE_TYPES = {"invoice_payment", "trust_transfer"}
OPERATING_EXPENSE_TYPES = {"expense_payment"}
OPERATING_REVERSAL_TYPES = {"payment_reversal"}
REVERSAL_REASON = "void_reversal"
DIRECT_PAYMENT_SOURCE = "direct"
TRUST_PAYMENT_SOURCE = "trust"
VALID_INVOICE_LINE_TYPES = {
    "legal_fee",
    "hourly_work",
    "flat_fee",
    "disbursement",
    "expense",
    "approved_billable_expense",
}
PROHIBITED_INVOICE_LINE_TYPES = {
    "trust_deposit",
    "retainer_deposit",
    "escrow",
    "client_funds",
    "property_funds",
    "trust_income",
    "trust_revenue",
    "invoice_retainer",
}
INVOICE_LINE_TYPE_ALIASES = {
    "time": "hourly_work",
    "billable_time": "hourly_work",
    "legal_service": "legal_fee",
    "billable_expense": "approved_billable_expense",
}


def normalize_currency(value: str | None) -> str:
    normalized = (value or "USD").strip().upper()
    if normalized not in {"USD", "JMD"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported currency")
    return normalized


def money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_invoice_line_type(line_type: str) -> str:
    normalized = line_type.strip().lower()
    normalized = INVOICE_LINE_TYPE_ALIASES.get(normalized, normalized)
    if normalized in PROHIBITED_INVOICE_LINE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice line items cannot represent trust deposits or client funds")
    if normalized not in VALID_INVOICE_LINE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invoice line item category")
    return normalized


def derive_invoice_status(invoice: Invoice) -> str:
    raw_status = (invoice.status or "draft").strip().lower()
    balance_due = money(getattr(invoice, "balance_due", ZERO))
    paid_amount = money(getattr(invoice, "paid_amount", ZERO))
    due_date = getattr(invoice, "due_date", None)
    today = date.today()
    if raw_status in {"cancelled", "void", "voided"}:
        return "cancelled"
    if balance_due <= ZERO and (paid_amount > ZERO or raw_status == "paid"):
        return "paid"
    if due_date is not None and due_date < today and raw_status not in {"draft"}:
        return "overdue"
    if raw_status in {"sent", "partially_paid", "overdue"}:
        return raw_status
    return "draft"


def summarize_invoice_payment_method(invoice: Invoice) -> str:
    payments = list(getattr(invoice, "payments", []) or [])
    active_sources = {payment.payment_source for payment in payments if getattr(payment, "voided_at", None) is None}
    if "direct" in active_sources and "trust" in active_sources:
        return "Mixed"
    if "direct" in active_sources:
        return "Direct"
    if "trust" in active_sources:
        return "Trust"
    if payments and any(getattr(payment, "voided_at", None) is not None for payment in payments):
        return "Voided/Reversed"
    return "Unpaid"


async def get_or_create_default_trust_account(db: AsyncSession, organization_id: int, currency: str) -> TrustAccount:
    currency = normalize_currency(currency)
    account = await db.scalar(
        select(TrustAccount).where(
            TrustAccount.organization_id == organization_id,
            TrustAccount.currency == currency,
            TrustAccount.is_default == True,
            TrustAccount.is_active == True,
        )
    )
    if account:
        return account
    now = utc_now()
    account = TrustAccount(
        organization_id=organization_id,
        name=f"Default {currency} Trust Account",
        currency=currency,
        account_type="pooled",
        is_default=True,
        opening_balance=ZERO,
        current_balance=ZERO,
        is_active=True,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.flush()
    return account


async def get_or_create_default_operating_account(db: AsyncSession, organization_id: int, currency: str) -> OperatingAccount:
    currency = normalize_currency(currency)
    account = await db.scalar(
        select(OperatingAccount).where(
            OperatingAccount.organization_id == organization_id,
            OperatingAccount.currency == currency,
            OperatingAccount.is_default == True,
            OperatingAccount.is_active == True,
        )
    )
    if account:
        return account
    now = utc_now()
    account = OperatingAccount(
        organization_id=organization_id,
        name=f"Default {currency} Operating Account",
        currency=currency,
        is_default=True,
        current_balance=ZERO,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.flush()
    return account


async def get_or_create_trust_ledger(
    db: AsyncSession,
    *,
    organization_id: int,
    trust_account_id: int,
    client_id: int,
    case_id: int,
) -> TrustLedger:
    ledger = await db.scalar(
        select(TrustLedger).where(
            TrustLedger.organization_id == organization_id,
            TrustLedger.trust_account_id == trust_account_id,
            TrustLedger.client_id == client_id,
            TrustLedger.case_id == case_id,
        )
    )
    if ledger:
        return ledger
    now = utc_now()
    ledger = TrustLedger(
        organization_id=organization_id,
        trust_account_id=trust_account_id,
        client_id=client_id,
        case_id=case_id,
        current_balance=ZERO,
        created_at=now,
        updated_at=now,
    )
    db.add(ledger)
    await db.flush()
    return ledger


async def validate_trust_context(
    db: AsyncSession,
    *,
    organization_id: int,
    trust_account_id: int,
    client_id: int,
    case_id: int,
    currency: str,
    linked_invoice_id: int | None = None,
) -> tuple[TrustAccount, Client, Case, Invoice | None]:
    account = await db.scalar(
        select(TrustAccount).where(
            TrustAccount.id == trust_account_id,
            TrustAccount.organization_id == organization_id,
            TrustAccount.is_active == True,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trust account not found")
    if account.currency != currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trust account currency mismatch")

    client = await db.scalar(select(Client).where(Client.id == client_id, Client.organization_id == organization_id))
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client not found")

    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == organization_id))
    if not case:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case not found")
    if case.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case/client mismatch")

    invoice = None
    if linked_invoice_id is not None:
        invoice = await db.scalar(select(Invoice).where(Invoice.id == linked_invoice_id, Invoice.organization_id == organization_id))
        if not invoice:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice not found")
        if invoice.client_id != client_id or invoice.case_id != case_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice/client/case mismatch")
    return account, client, case, invoice


def _trust_delta(transaction_type: str, amount: Decimal, adjustment_direction: str | None = None) -> Decimal:
    amount = money(amount)
    if transaction_type == "adjustment":
        if adjustment_direction == "decrease":
            return -amount
        return amount
    if transaction_type in TRUST_INFLOW_TYPES:
        return amount
    if transaction_type in TRUST_OUTFLOW_TYPES:
        return -amount
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported trust transaction type")


def _trust_reversal_direction(original: TrustTransaction) -> str:
    if original.transaction_type == "deposit":
        return "decrease"
    if original.transaction_type in {"disbursement", "refund"}:
        return "increase"
    if original.transaction_type == "adjustment":
        return "increase" if original.adjustment_direction == "decrease" else "decrease"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported transaction type for reversal")


def _assert_description(value: str | None, *, field_name: str = "description") -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} is required")
    return normalized


def update_invoice_payment_state(invoice: Invoice) -> Invoice:
    invoice.paid_amount = money(invoice.paid_amount)
    invoice.total = money(invoice.total)
    invoice.balance_due = money(max(ZERO, invoice.total - invoice.paid_amount))
    if invoice.balance_due == ZERO:
        invoice.status = "paid"
    elif invoice.paid_amount > ZERO:
        invoice.status = "partially_paid"
    elif invoice.status not in {"draft", "cancelled", "void", "voided"}:
        invoice.status = "sent"
    return invoice


async def refresh_invoice_payment_totals(db: AsyncSession, invoice: Invoice) -> Invoice:
    paid_amount = await db.scalar(
        select(func.coalesce(func.sum(InvoicePayment.amount), 0)).where(
            InvoicePayment.organization_id == invoice.organization_id,
            InvoicePayment.invoice_id == invoice.id,
            InvoicePayment.voided_at.is_(None),
        )
    )
    invoice.paid_amount = money(paid_amount)
    update_invoice_payment_state(invoice)
    invoice.updated_at = utc_now()
    return invoice


async def get_invoice_currency(db: AsyncSession, organization_id: int, invoice: Invoice, explicit_currency: str | None = None) -> str:
    if explicit_currency is not None:
        return normalize_currency(explicit_currency)
    invoice_currency = getattr(invoice, "currency", None)
    if invoice_currency:
        return normalize_currency(invoice_currency)
    client = await db.scalar(select(Client).where(Client.id == invoice.client_id, Client.organization_id == organization_id))
    return normalize_currency(getattr(client, "billing_currency", None))


async def get_trust_account_balance(db: AsyncSession, organization_id: int, trust_account_id: int, currency: str) -> Decimal:
    balance = await db.scalar(
        select(func.coalesce(TrustAccount.current_balance, 0)).where(
            TrustAccount.organization_id == organization_id,
            TrustAccount.id == trust_account_id,
            TrustAccount.currency == normalize_currency(currency),
        )
    )
    return money(balance)


async def get_client_trust_balance(db: AsyncSession, organization_id: int, client_id: int, currency: str) -> Decimal:
    balance = await db.scalar(
        select(func.coalesce(func.sum(TrustLedger.current_balance), 0))
        .join(TrustAccount, TrustAccount.id == TrustLedger.trust_account_id)
        .where(
            TrustLedger.organization_id == organization_id,
            TrustLedger.client_id == client_id,
            TrustAccount.currency == normalize_currency(currency),
            TrustAccount.is_active == True,
        )
    )
    return money(balance)


async def get_matter_trust_balance(db: AsyncSession, organization_id: int, case_id: int, currency: str) -> Decimal:
    balance = await db.scalar(
        select(func.coalesce(func.sum(TrustLedger.current_balance), 0))
        .join(TrustAccount, TrustAccount.id == TrustLedger.trust_account_id)
        .where(
            TrustLedger.organization_id == organization_id,
            TrustLedger.case_id == case_id,
            TrustAccount.currency == normalize_currency(currency),
            TrustAccount.is_active == True,
        )
    )
    return money(balance)


async def validate_sufficient_trust_balance(
    db: AsyncSession,
    *,
    organization_id: int,
    client_id: int,
    case_id: int,
    amount: Decimal,
    currency: str,
) -> Decimal:
    balance = await get_matter_trust_balance(db, organization_id, case_id, currency)
    if balance < money(amount):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient matter trust balance")
    client_balance = await get_client_trust_balance(db, organization_id, client_id, currency)
    if client_balance < money(amount):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient client trust balance")
    return balance


async def create_operating_transaction(
    db: AsyncSession,
    *,
    organization_id: int,
    operating_account_id: int,
    transaction_type: str,
    amount: Decimal,
    currency: str,
    transaction_date: date,
    description: str | None,
    created_by_id: int,
    linked_invoice_id: int | None = None,
    linked_trust_transaction_id: int | None = None,
    linked_payment_id: int | None = None,
    linked_expense_id: int | None = None,
    reversal_of_id: int | None = None,
) -> OperatingTransaction:
    currency = normalize_currency(currency)
    account = await db.scalar(
        select(OperatingAccount).where(
            OperatingAccount.id == operating_account_id,
            OperatingAccount.organization_id == organization_id,
            OperatingAccount.currency == currency,
            OperatingAccount.is_active == True,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Operating account not found")

    amount = money(amount)
    if amount <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than zero")

    delta = amount if transaction_type in OPERATING_REVENUE_TYPES | {"adjustment"} else -amount
    account.current_balance = money(account.current_balance + delta)
    account.updated_at = utc_now()

    txn = OperatingTransaction(
        organization_id=organization_id,
        operating_account_id=operating_account_id,
        transaction_type=transaction_type,
        amount=amount,
        currency=currency,
        transaction_date=transaction_date,
        description=description,
        linked_invoice_id=linked_invoice_id,
        linked_trust_transaction_id=linked_trust_transaction_id,
        linked_payment_id=linked_payment_id,
        linked_expense_id=linked_expense_id,
        reversal_of_id=reversal_of_id,
        created_by_id=created_by_id,
        created_at=utc_now(),
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )
    db.add(txn)
    await db.flush()
    return txn


async def create_trust_receipt(
    db: AsyncSession,
    *,
    organization_id: int,
    trust_transaction: TrustTransaction,
    issued_by_id: int,
) -> TrustReceipt:
    receipt = TrustReceipt(
        organization_id=organization_id,
        trust_transaction_id=trust_transaction.id,
        receipt_number=f"TR-{trust_transaction.transaction_date.year}-{trust_transaction.id:06d}",
        client_id=trust_transaction.client_id,
        case_id=trust_transaction.case_id,
        amount=trust_transaction.amount,
        currency=trust_transaction.currency,
        payment_method=trust_transaction.payment_method,
        description=trust_transaction.description,
        issued_at=utc_now(),
        issued_by_id=issued_by_id,
        pdf_path=None,
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )
    db.add(receipt)
    await db.flush()
    return receipt


async def create_trust_transaction(
    db: AsyncSession,
    *,
    organization_id: int,
    trust_account_id: int,
    client_id: int,
    case_id: int,
    transaction_type: str,
    amount: Decimal,
    currency: str,
    transaction_date: date,
    created_by_id: int,
    description: str | None = None,
    payee_name: str | None = None,
    payee_type: str | None = None,
    payment_method: str | None = None,
    reference_number: str | None = None,
    linked_invoice_id: int | None = None,
    adjustment_direction: str | None = None,
    adjustment_reason: str | None = None,
    reversal_of_id: int | None = None,
    audit_request: dict | None = None,
) -> tuple[TrustTransaction, TrustReceipt | None, OperatingTransaction | None]:
    transaction_type = transaction_type.strip().lower()
    currency = normalize_currency(currency)
    if transaction_type not in TRUST_ALL_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported trust transaction type")
    if transaction_type == "transfer_to_operating" and linked_invoice_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transfer_to_operating is reserved for Phase C invoice-linked workflow")

    amount = money(amount)
    if amount <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than zero")
    description = _assert_description(description)
    if transaction_type == "disbursement" and not (payee_name or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payee_name is required for disbursements")
    if transaction_type == "adjustment":
        if adjustment_direction not in {"increase", "decrease"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="adjustment_direction is required for adjustments")
        adjustment_reason = _assert_description(adjustment_reason, field_name="adjustment_reason")

    account, _, case, invoice = await validate_trust_context(
        db,
        organization_id=organization_id,
        trust_account_id=trust_account_id,
        client_id=client_id,
        case_id=case_id,
        currency=currency,
        linked_invoice_id=linked_invoice_id,
    )
    ledger = await get_or_create_trust_ledger(
        db,
        organization_id=organization_id,
        trust_account_id=trust_account_id,
        client_id=client_id,
        case_id=case_id,
    )

    delta = _trust_delta(transaction_type, amount, adjustment_direction=adjustment_direction)
    if delta < ZERO:
        await validate_sufficient_trust_balance(
            db,
            organization_id=organization_id,
            client_id=client_id,
            case_id=case_id,
            amount=abs(delta),
            currency=currency,
        )

    now = utc_now()
    previous_ledger_balance = money(ledger.current_balance)
    previous_account_balance = money(account.current_balance)
    ledger.current_balance = money(ledger.current_balance + delta)
    ledger.updated_at = now
    account.current_balance = money(account.current_balance + delta)
    account.updated_at = now

    txn = TrustTransaction(
        organization_id=organization_id,
        trust_account_id=trust_account_id,
        ledger_id=ledger.id,
        client_id=client_id,
        case_id=case.id,
        linked_invoice_id=invoice.id if invoice else None,
        transaction_type=transaction_type,
        amount=amount,
        currency=currency,
        description=description,
        payee_name=(payee_name or None),
        payee_type=(payee_type or None),
        payment_method=payment_method,
        reference_number=reference_number,
        adjustment_reason=adjustment_reason,
        adjustment_direction=adjustment_direction,
        reversal_of_id=reversal_of_id,
        transaction_date=transaction_date,
        created_by_id=created_by_id,
        created_at=now,
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )
    db.add(txn)
    await db.flush()

    receipt = None
    operating_txn = None
    if transaction_type == "deposit":
        receipt = await create_trust_receipt(db, organization_id=organization_id, trust_transaction=txn, issued_by_id=created_by_id)

    if invoice is not None and transaction_type == "transfer_to_operating":
        invoice.paid_amount = money((invoice.paid_amount or ZERO) + amount)
        update_invoice_payment_state(invoice)

        operating_account = await get_or_create_default_operating_account(db, organization_id, currency)
        operating_txn = await create_operating_transaction(
            db,
            organization_id=organization_id,
            operating_account_id=operating_account.id,
            transaction_type="trust_transfer",
            amount=amount,
            currency=currency,
            transaction_date=transaction_date,
            description=description or f"Trust transfer for invoice {invoice.invoice_number}",
            created_by_id=created_by_id,
            linked_invoice_id=invoice.id,
            linked_trust_transaction_id=txn.id,
        )

    if audit_request is not None:
        await log_audit_event(
            db,
            organization_id=organization_id,
            user_id=created_by_id,
            action=f"trust_{transaction_type}",
            entity_type="trust_transaction",
            entity_id=str(txn.id),
            description=f"Trust {transaction_type} recorded",
            metadata_json={
                "client_id": client_id,
                "case_id": case.id,
                "linked_invoice_id": invoice.id if invoice else None,
                "currency": currency,
                "payee_name": payee_name,
                "payee_type": payee_type,
                "adjustment_reason": adjustment_reason,
                "adjustment_direction": adjustment_direction,
                "reversal_of_id": reversal_of_id,
                "before_values": {
                    "ledger_balance": str(previous_ledger_balance),
                    "account_balance": str(previous_account_balance),
                },
                "after_values": {
                    "ledger_balance": str(ledger.current_balance),
                    "account_balance": str(account.current_balance),
                    "receipt_id": receipt.id if receipt else None,
                },
            },
            ip_address=audit_request.get("ip_address"),
            user_agent=audit_request.get("user_agent"),
        )
    return txn, receipt, operating_txn


async def get_trust_transaction_or_404(db: AsyncSession, organization_id: int, transaction_id: int) -> TrustTransaction:
    transaction = await db.scalar(
        select(TrustTransaction).where(
            TrustTransaction.id == transaction_id,
            TrustTransaction.organization_id == organization_id,
        )
    )
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust transaction not found")
    return transaction


async def void_trust_transaction(
    db: AsyncSession,
    *,
    organization_id: int,
    transaction_id: int,
    void_reason: str,
    voided_by_id: int,
    audit_request: dict | None = None,
) -> tuple[TrustTransaction, TrustTransaction]:
    original = await get_trust_transaction_or_404(db, organization_id, transaction_id)
    if original.voided_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trust transaction already voided")
    if original.reversal_of_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reversal transactions cannot be voided")
    if original.transaction_type == "transfer_to_operating":
        if original.linked_invoice_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice-linked trust transfers must be voided through the invoice payment void workflow",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transfer_to_operating void workflow is reserved for invoice payment reversals")

    now = utc_now()
    original.voided_at = now
    original.voided_by_id = voided_by_id
    original.void_reason = void_reason.strip()

    if original.receipt is not None:
        original.receipt.voided_at = now
        original.receipt.voided_by_id = voided_by_id
        original.receipt.void_reason = original.void_reason

    reversal_direction = _trust_reversal_direction(original)
    reversal_description = f"Reversal of trust transaction #{original.id}: {original.void_reason}"
    reversal_txn, _, _ = await create_trust_transaction(
        db,
        organization_id=organization_id,
        trust_account_id=original.trust_account_id,
        client_id=original.client_id,
        case_id=original.case_id,
        transaction_type="adjustment",
        amount=original.amount,
        currency=original.currency,
        transaction_date=original.transaction_date,
        created_by_id=voided_by_id,
        description=reversal_description,
        payee_name=original.payee_name,
        payee_type=original.payee_type,
        payment_method=original.payment_method,
        reference_number=original.reference_number,
        adjustment_direction=reversal_direction,
        adjustment_reason=REVERSAL_REASON,
        reversal_of_id=original.id,
        audit_request=audit_request,
    )
    await log_audit_event(
        db,
        organization_id=organization_id,
        user_id=voided_by_id,
        action="trust_transaction_voided",
        entity_type="trust_transaction",
        entity_id=str(original.id),
        description=f"Voided trust transaction #{original.id}",
        metadata_json={
            "void_reason": original.void_reason,
            "reversal_transaction_id": reversal_txn.id,
            "receipt_voided": bool(original.receipt),
        },
        ip_address=audit_request.get("ip_address") if audit_request else None,
        user_agent=audit_request.get("user_agent") if audit_request else None,
    )
    return original, reversal_txn


async def get_client_ledgers(db: AsyncSession, organization_id: int, currency: str | None = None) -> list[dict]:
    query = (
        select(
            TrustLedger.client_id,
            Client.name.label("client_name"),
            TrustAccount.currency,
            func.coalesce(func.sum(TrustLedger.current_balance), 0).label("balance"),
        )
        .join(Client, Client.id == TrustLedger.client_id)
        .join(TrustAccount, TrustAccount.id == TrustLedger.trust_account_id)
        .where(TrustLedger.organization_id == organization_id, TrustAccount.is_active == True)
        .group_by(TrustLedger.client_id, Client.name, TrustAccount.currency)
        .order_by(Client.name.asc(), TrustAccount.currency.asc())
    )
    if currency is not None:
        query = query.where(TrustAccount.currency == normalize_currency(currency))
    rows = (await db.execute(query)).all()
    return [
        {
            "client_id": row.client_id,
            "client_name": row.client_name,
            "currency": row.currency,
            "balance": money(row.balance),
        }
        for row in rows
    ]


async def get_matter_ledgers(db: AsyncSession, organization_id: int, currency: str | None = None) -> list[dict]:
    query = (
        select(
            TrustLedger.case_id,
            Case.title.label("case_title"),
            TrustLedger.client_id,
            Client.name.label("client_name"),
            TrustAccount.currency,
            func.coalesce(func.sum(TrustLedger.current_balance), 0).label("balance"),
        )
        .join(Case, Case.id == TrustLedger.case_id)
        .join(Client, Client.id == TrustLedger.client_id)
        .join(TrustAccount, TrustAccount.id == TrustLedger.trust_account_id)
        .where(TrustLedger.organization_id == organization_id, TrustAccount.is_active == True)
        .group_by(TrustLedger.case_id, Case.title, TrustLedger.client_id, Client.name, TrustAccount.currency)
        .order_by(Case.title.asc(), TrustAccount.currency.asc())
    )
    if currency is not None:
        query = query.where(TrustAccount.currency == normalize_currency(currency))
    rows = (await db.execute(query)).all()
    return [
        {
            "case_id": row.case_id,
            "case_title": row.case_title,
            "client_id": row.client_id,
            "client_name": row.client_name,
            "currency": row.currency,
            "balance": money(row.balance),
        }
        for row in rows
    ]


async def log_finance_guardrail_event(
    db: AsyncSession,
    *,
    organization_id: int,
    user_id: int | None,
    action: str,
    detail: str,
    client_id: int | None = None,
    case_id: int | None = None,
) -> AuditLog:
    return await log_audit_event(
        db,
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        entity_type="finance_guardrail",
        description=detail,
        metadata_json={"client_id": client_id, "case_id": case_id},
    )


async def build_accounting_summary(db: AsyncSession, organization_id: int) -> list[dict]:
    expense_rows = (
        await db.execute(
            select(
                OperatingTransaction.currency,
                func.coalesce(func.sum(OperatingTransaction.amount), 0).label("total"),
            )
            .where(
                OperatingTransaction.organization_id == organization_id,
                OperatingTransaction.transaction_type.in_(tuple(OPERATING_EXPENSE_TYPES)),
            )
            .group_by(OperatingTransaction.currency)
        )
    ).all()
    balance_rows = (
        await db.execute(
            select(
                OperatingAccount.currency,
                func.coalesce(func.sum(OperatingAccount.current_balance), 0).label("total"),
            )
            .where(
                OperatingAccount.organization_id == organization_id,
                OperatingAccount.is_active == True,
            )
            .group_by(OperatingAccount.currency)
        )
    ).all()
    payment_rows = (
        await db.execute(
            select(
                InvoicePayment.currency,
                InvoicePayment.payment_source,
                func.coalesce(func.sum(InvoicePayment.amount), 0).label("total"),
            )
            .where(
                InvoicePayment.organization_id == organization_id,
                InvoicePayment.voided_at.is_(None),
            )
            .group_by(InvoicePayment.currency, InvoicePayment.payment_source)
        )
    ).all()
    tax_rows = (
        await db.execute(
            select(
                InvoicePayment.currency,
                func.coalesce(func.sum((Invoice.tax_amount * InvoicePayment.amount) / func.nullif(Invoice.total, 0)), 0).label("total"),
            )
            .join(Invoice, Invoice.id == InvoicePayment.invoice_id)
            .where(
                InvoicePayment.organization_id == organization_id,
                InvoicePayment.voided_at.is_(None),
            )
            .group_by(InvoicePayment.currency)
        )
    ).all()

    expense_map = defaultdict(lambda: ZERO, {row.currency: money(row.total) for row in expense_rows})
    balance_map = defaultdict(lambda: ZERO, {row.currency: money(row.total) for row in balance_rows})
    tax_map = defaultdict(lambda: ZERO, {row.currency: money(row.total) for row in tax_rows})
    revenue_map = defaultdict(lambda: ZERO)
    direct_payment_map = defaultdict(lambda: ZERO)
    trust_transfer_map = defaultdict(lambda: ZERO)
    for row in payment_rows:
        total = money(row.total)
        revenue_map[row.currency] += total
        if row.payment_source == DIRECT_PAYMENT_SOURCE:
            direct_payment_map[row.currency] += total
        elif row.payment_source == TRUST_PAYMENT_SOURCE:
            trust_transfer_map[row.currency] += total
    currencies = sorted(set(revenue_map) | set(expense_map) | set(balance_map) | set(direct_payment_map) | set(trust_transfer_map) | set(tax_map))
    return [
        {
            "currency": currency,
            "revenue": money(revenue_map[currency]),
            "expenses": expense_map[currency],
            "profit": money(revenue_map[currency] - expense_map[currency]),
            "operating_balance": balance_map[currency],
            "direct_payment_total": money(direct_payment_map[currency]),
            "trust_transfer_total": money(trust_transfer_map[currency]),
            "tax_payable": tax_map[currency],
        }
        for currency in currencies
    ]


async def get_invoice_payment_or_404(db: AsyncSession, organization_id: int, payment_id: int) -> InvoicePayment:
    payment = await db.scalar(
        select(InvoicePayment).where(
            InvoicePayment.id == payment_id,
            InvoicePayment.organization_id == organization_id,
        )
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice payment not found")
    return payment


async def get_operating_transaction_or_404(db: AsyncSession, organization_id: int, transaction_id: int) -> OperatingTransaction:
    operating_transaction = await db.scalar(
        select(OperatingTransaction).where(
            OperatingTransaction.id == transaction_id,
            OperatingTransaction.organization_id == organization_id,
        )
    )
    if not operating_transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operating transaction not found")
    return operating_transaction


def apply_transaction_filters(query: Select, *, model, filters: dict) -> Select:
    if filters.get("client_id") is not None:
        query = query.where(model.client_id == filters["client_id"])
    if filters.get("case_id") is not None:
        query = query.where(model.case_id == filters["case_id"])
    if filters.get("trust_account_id") is not None:
        query = query.where(model.trust_account_id == filters["trust_account_id"])
    if filters.get("transaction_type") is not None:
        query = query.where(model.transaction_type == filters["transaction_type"])
    if filters.get("currency") is not None:
        query = query.where(model.currency == normalize_currency(filters["currency"]))
    if filters.get("date_from") is not None:
        query = query.where(model.transaction_date >= filters["date_from"])
    if filters.get("date_to") is not None:
        query = query.where(model.transaction_date <= filters["date_to"])
    if not filters.get("include_voided"):
        query = query.where(model.voided_at.is_(None))
    return query


async def create_invoice_payment_record(
    db: AsyncSession,
    *,
    organization_id: int,
    invoice: Invoice,
    amount: Decimal,
    currency: str,
    payment_source: str,
    payment_method: str | None,
    reference_number: str | None,
    description: str | None,
    paid_at: date,
    created_by_id: int,
    linked_trust_transaction_id: int | None = None,
    linked_operating_transaction_id: int | None = None,
) -> InvoicePayment:
    payment = InvoicePayment(
        organization_id=organization_id,
        invoice_id=invoice.id,
        amount=money(amount),
        currency=normalize_currency(currency),
        payment_method=payment_method,
        payment_source=payment_source,
        paid_at=paid_at,
        reference_number=reference_number,
        description=description,
        linked_trust_transaction_id=linked_trust_transaction_id,
        linked_operating_transaction_id=linked_operating_transaction_id,
        created_by_id=created_by_id,
        created_at=utc_now(),
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )
    db.add(payment)
    await db.flush()
    return payment


def validate_invoice_payment_amount(invoice: Invoice, amount: Decimal) -> Decimal:
    amount = money(amount)
    if amount <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than zero")
    if invoice.balance_due <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is already fully paid")
    if amount > money(invoice.balance_due):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount cannot exceed invoice balance due")
    return amount


def validate_invoice_payable(invoice: Invoice) -> None:
    if invoice.status in {"cancelled", "void", "voided"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancelled or void invoices cannot accept payments")


def validate_invoice_trust_payable(invoice: Invoice) -> None:
    validate_invoice_payable(invoice)
    if invoice.case_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice must be linked to a matter to apply trust")


async def create_invoice_payment_operating_transaction(
    db: AsyncSession,
    *,
    organization_id: int,
    invoice: Invoice,
    created_by_id: int,
    transaction_date: date,
    amount: Decimal | None = None,
    payment_method: str | None = None,
    reference_number: str | None = None,
    description: str | None = None,
) -> tuple[OperatingTransaction, InvoicePayment]:
    validate_invoice_payable(invoice)
    payment_amount = validate_invoice_payment_amount(invoice, amount if amount is not None else invoice.balance_due)
    currency = await get_invoice_currency(db, organization_id, invoice)
    operating_account = await get_or_create_default_operating_account(db, organization_id, currency)
    operating_txn = await create_operating_transaction(
        db,
        organization_id=organization_id,
        operating_account_id=operating_account.id,
        transaction_type="invoice_payment",
        amount=payment_amount,
        currency=currency,
        transaction_date=transaction_date,
        description=description or f"Invoice payment for {invoice.invoice_number}",
        created_by_id=created_by_id,
        linked_invoice_id=invoice.id,
    )
    invoice.paid_amount = money((invoice.paid_amount or ZERO) + payment_amount)
    update_invoice_payment_state(invoice)
    invoice.updated_at = utc_now()
    payment = await create_invoice_payment_record(
        db,
        organization_id=organization_id,
        invoice=invoice,
        amount=payment_amount,
        currency=currency,
        payment_source=DIRECT_PAYMENT_SOURCE,
        payment_method=payment_method,
        reference_number=reference_number,
        description=description or f"Direct payment applied to {invoice.invoice_number}",
        paid_at=transaction_date,
        created_by_id=created_by_id,
        linked_operating_transaction_id=operating_txn.id,
    )
    operating_txn.linked_payment_id = payment.id
    return operating_txn, payment


async def apply_trust_to_invoice(
    db: AsyncSession,
    *,
    organization_id: int,
    invoice: Invoice,
    amount: Decimal,
    created_by_id: int,
    trust_account_id: int | None = None,
    currency: str | None = None,
    description: str | None = None,
    reference_number: str | None = None,
    payment_date: date | None = None,
    audit_request: dict | None = None,
) -> tuple[Invoice, InvoicePayment, TrustTransaction, OperatingTransaction]:
    validate_invoice_trust_payable(invoice)
    payment_amount = validate_invoice_payment_amount(invoice, amount)
    resolved_currency = await get_invoice_currency(db, organization_id, invoice, currency)
    if trust_account_id is None:
        trust_account = await get_or_create_default_trust_account(db, organization_id, resolved_currency)
        trust_account_id = trust_account.id
    description = description or f"Applied trust funds to Invoice {invoice.invoice_number}"
    trust_txn, _, operating_txn = await create_trust_transaction(
        db,
        organization_id=organization_id,
        trust_account_id=trust_account_id,
        client_id=invoice.client_id,
        case_id=invoice.case_id,
        transaction_type="transfer_to_operating",
        amount=payment_amount,
        currency=resolved_currency,
        transaction_date=payment_date or date.today(),
        created_by_id=created_by_id,
        description=description,
        reference_number=reference_number,
        linked_invoice_id=invoice.id,
        audit_request=audit_request,
    )
    if operating_txn is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Trust transfer operating transaction was not created")
    invoice.updated_at = utc_now()
    payment = await create_invoice_payment_record(
        db,
        organization_id=organization_id,
        invoice=invoice,
        amount=payment_amount,
        currency=resolved_currency,
        payment_source=TRUST_PAYMENT_SOURCE,
        payment_method="trust_transfer",
        reference_number=reference_number,
        description=description,
        paid_at=payment_date or date.today(),
        created_by_id=created_by_id,
        linked_trust_transaction_id=trust_txn.id,
        linked_operating_transaction_id=operating_txn.id,
    )
    operating_txn.linked_payment_id = payment.id
    await log_audit_event(
        db,
        organization_id=organization_id,
        user_id=created_by_id,
        action="invoice_trust_applied",
        entity_type="invoice",
        entity_id=str(invoice.id),
        description=f"Applied trust funds to invoice {invoice.invoice_number}",
        metadata_json={
            "invoice_id": invoice.id,
            "payment_id": payment.id,
            "trust_transaction_id": trust_txn.id,
            "operating_transaction_id": operating_txn.id,
            "amount": str(payment_amount),
            "currency": resolved_currency,
        },
        ip_address=audit_request.get("ip_address") if audit_request else None,
        user_agent=audit_request.get("user_agent") if audit_request else None,
    )
    return invoice, payment, trust_txn, operating_txn


async def void_invoice_payment(
    db: AsyncSession,
    *,
    organization_id: int,
    invoice: Invoice,
    payment_id: int,
    void_reason: str,
    voided_by_id: int,
    void_date: date | None = None,
    description: str | None = None,
    audit_request: dict | None = None,
) -> tuple[InvoicePayment, OperatingTransaction, TrustTransaction | None]:
    payment = await get_invoice_payment_or_404(db, organization_id, payment_id)
    if payment.invoice_id != invoice.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment does not belong to invoice")
    if payment.voided_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invoice payment already voided")

    normalized_reason = _assert_description(void_reason, field_name="void_reason")
    reversal_date = void_date or date.today()
    now = utc_now()
    invoice_before = {
        "status": invoice.status,
        "paid_amount": str(money(invoice.paid_amount)),
        "balance_due": str(money(invoice.balance_due)),
    }
    payment.voided_at = now
    payment.voided_by_id = voided_by_id
    payment.void_reason = normalized_reason

    original_operating_transaction: OperatingTransaction | None = None
    if payment.linked_operating_transaction_id is not None:
        original_operating_transaction = await get_operating_transaction_or_404(db, organization_id, payment.linked_operating_transaction_id)
        original_operating_transaction.voided_at = now
        original_operating_transaction.voided_by_id = voided_by_id
        original_operating_transaction.void_reason = normalized_reason

    reversal_description = description or f"Reversal of invoice payment #{payment.id}: {normalized_reason}"
    reversal_trust_transaction: TrustTransaction | None = None
    linked_trust_transaction_id: int | None = None

    if payment.payment_source == TRUST_PAYMENT_SOURCE:
        if payment.linked_trust_transaction_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trust-backed payment is missing its trust transfer record")
        original_trust_transaction = await get_trust_transaction_or_404(db, organization_id, payment.linked_trust_transaction_id)
        if original_trust_transaction.transaction_type != "transfer_to_operating":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Linked trust transaction is not an invoice trust transfer")
        original_trust_transaction.voided_at = now
        original_trust_transaction.voided_by_id = voided_by_id
        original_trust_transaction.void_reason = normalized_reason
        reversal_trust_transaction, _, _ = await create_trust_transaction(
            db,
            organization_id=organization_id,
            trust_account_id=original_trust_transaction.trust_account_id,
            client_id=original_trust_transaction.client_id,
            case_id=original_trust_transaction.case_id,
            transaction_type="adjustment",
            amount=payment.amount,
            currency=payment.currency,
            transaction_date=reversal_date,
            created_by_id=voided_by_id,
            description=reversal_description,
            payment_method=original_trust_transaction.payment_method,
            reference_number=original_trust_transaction.reference_number,
            linked_invoice_id=invoice.id,
            adjustment_direction="increase",
            adjustment_reason=REVERSAL_REASON,
            reversal_of_id=original_trust_transaction.id,
            audit_request=audit_request,
        )
        linked_trust_transaction_id = reversal_trust_transaction.id

    if original_operating_transaction is None:
        operating_account = await get_or_create_default_operating_account(db, organization_id, payment.currency)
        operating_account_id = operating_account.id
        reversal_of_id = None
    else:
        operating_account_id = original_operating_transaction.operating_account_id
        reversal_of_id = original_operating_transaction.id
    reversal_operating_transaction = await create_operating_transaction(
        db,
        organization_id=organization_id,
        operating_account_id=operating_account_id,
        transaction_type="payment_reversal",
        amount=payment.amount,
        currency=payment.currency,
        transaction_date=reversal_date,
        description=reversal_description,
        created_by_id=voided_by_id,
        linked_invoice_id=invoice.id,
        linked_trust_transaction_id=linked_trust_transaction_id,
        linked_payment_id=payment.id,
        reversal_of_id=reversal_of_id,
    )
    await refresh_invoice_payment_totals(db, invoice)
    await log_audit_event(
        db,
        organization_id=organization_id,
        user_id=voided_by_id,
        action="invoice_payment_voided",
        entity_type="invoice_payment",
        entity_id=str(payment.id),
        description=f"Voided invoice payment #{payment.id}",
        metadata_json={
            "invoice_id": invoice.id,
            "payment_source": payment.payment_source,
            "void_reason": normalized_reason,
            "reversal_operating_transaction_id": reversal_operating_transaction.id,
            "reversal_trust_transaction_id": reversal_trust_transaction.id if reversal_trust_transaction else None,
            "before_values": invoice_before,
            "after_values": {
                "status": invoice.status,
                "paid_amount": str(invoice.paid_amount),
                "balance_due": str(invoice.balance_due),
            },
        },
        ip_address=audit_request.get("ip_address") if audit_request else None,
        user_agent=audit_request.get("user_agent") if audit_request else None,
    )
    return payment, reversal_operating_transaction, reversal_trust_transaction
