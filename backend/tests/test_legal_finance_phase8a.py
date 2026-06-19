from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import AsyncIterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import deps as deps_module
from app.main import app
from app.models.enums import RecordStatus, UserRole
from app.models.invoice_payment import InvoicePayment
from app.models.operating_transaction import OperatingTransaction
from app.models.trust_receipt import TrustReceipt
from app.models.trust_transaction import TrustTransaction
from app.services.finance import (
    REVERSAL_REASON,
    apply_transaction_filters,
    apply_trust_to_invoice,
    build_accounting_summary,
    create_invoice_payment_operating_transaction,
    create_trust_transaction,
    derive_invoice_status,
    get_client_ledgers,
    get_matter_ledgers,
    summarize_invoice_payment_method,
    validate_invoice_line_type,
    void_invoice_payment,
    void_trust_transaction,
)


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


class FinanceServiceDB:
    def __init__(self, scalars: list, execute_rows: list[list[SimpleNamespace]] | None = None):
        self.scalars = list(scalars)
        self.execute_rows = list(execute_rows or [])
        self.added: list[object] = []
        self.commits = 0

    async def scalar(self, *args, **kwargs):
        if not self.scalars:
            raise AssertionError("Unexpected scalar() call")
        return self.scalars.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        next_id = 100
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", next_id)
                next_id += 1

    async def commit(self):
        self.commits += 1

    async def execute(self, query, *args, **kwargs):
        class _Res:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        if not self.execute_rows:
            raise AssertionError("Unexpected execute() call")
        return _Res(self.execute_rows.pop(0))


class AccountingSummaryDB:
    def __init__(self, execute_rows: list[list[SimpleNamespace]]):
        self.execute_rows = list(execute_rows)

    async def execute(self, query, *args, **kwargs):
        text = str(query).lower()
        assert "trust_" not in text

        class _Res:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Res(self.execute_rows.pop(0))


def _override_client(user: DummyUser, db):
    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def _trust_account(balance: str = "0.00", *, account_id: int = 1, org_id: int = 7, currency: str = "USD"):
    return SimpleNamespace(id=account_id, organization_id=org_id, currency=currency, is_active=True, current_balance=Decimal(balance), updated_at=datetime.now(timezone.utc))


def _client(*, client_id: int = 5, org_id: int = 7):
    return SimpleNamespace(id=client_id, organization_id=org_id, name=f"Client {client_id}")


def _case(*, case_id: int = 9, org_id: int = 7, client_id: int = 5):
    return SimpleNamespace(id=case_id, organization_id=org_id, client_id=client_id, title=f"Case {case_id}")


def _ledger(balance: str = "0.00", *, ledger_id: int = 3, org_id: int = 7, account_id: int = 1, client_id: int = 5, case_id: int = 9):
    return SimpleNamespace(
        id=ledger_id,
        organization_id=org_id,
        trust_account_id=account_id,
        client_id=client_id,
        case_id=case_id,
        current_balance=Decimal(balance),
        updated_at=datetime.now(timezone.utc),
    )


def _operating_account(balance: str = "0.00", *, account_id: int = 8, org_id: int = 7, currency: str = "USD"):
    return SimpleNamespace(id=account_id, organization_id=org_id, currency=currency, is_active=True, current_balance=Decimal(balance), updated_at=datetime.now(timezone.utc))


def _invoice(
    *,
    invoice_id: int = 30,
    org_id: int = 7,
    client_id: int = 5,
    case_id: int | None = 9,
    total: str = "200.00",
    paid_amount: str = "0.00",
    status: str = "sent",
):
    total_d = Decimal(total)
    paid_d = Decimal(paid_amount)
    return SimpleNamespace(
        id=invoice_id,
        organization_id=org_id,
        client_id=client_id,
        case_id=case_id,
        invoice_number=f"INV-2026-{invoice_id:04d}",
        total=total_d,
        paid_amount=paid_d,
        balance_due=total_d - paid_d,
        status=status,
        tax_amount=Decimal("30.00"),
        updated_at=datetime.now(timezone.utc),
    )


def _receipt(*, transaction_id: int = 11):
    return TrustReceipt(
        id=90,
        organization_id=7,
        trust_transaction_id=transaction_id,
        receipt_number="TR-2026-000011",
        client_id=5,
        case_id=9,
        amount=Decimal("100.00"),
        currency="USD",
        payment_method="wire",
        description="Deposit receipt",
        issued_at=datetime.now(timezone.utc),
        issued_by_id=22,
        pdf_path=None,
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )


def _payment(
    *,
    payment_id: int = 40,
    invoice_id: int = 30,
    source: str = "direct",
    amount: str = "100.00",
    currency: str = "USD",
    linked_trust_transaction_id: int | None = None,
    linked_operating_transaction_id: int | None = 70,
):
    return InvoicePayment(
        id=payment_id,
        organization_id=7,
        invoice_id=invoice_id,
        amount=Decimal(amount),
        currency=currency,
        payment_method="wire",
        payment_source=source,
        paid_at=date(2026, 6, 17),
        reference_number="PMT-1",
        description="Payment",
        linked_trust_transaction_id=linked_trust_transaction_id,
        linked_operating_transaction_id=linked_operating_transaction_id,
        created_by_id=22,
        created_at=datetime.now(timezone.utc),
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )


def _operating_transaction(
    *,
    txn_id: int = 70,
    transaction_type: str = "invoice_payment",
    amount: str = "100.00",
    currency: str = "USD",
    operating_account_id: int = 8,
    linked_invoice_id: int = 30,
    linked_trust_transaction_id: int | None = None,
):
    return OperatingTransaction(
        id=txn_id,
        organization_id=7,
        operating_account_id=operating_account_id,
        transaction_type=transaction_type,
        amount=Decimal(amount),
        currency=currency,
        transaction_date=date(2026, 6, 17),
        description="Operating entry",
        linked_invoice_id=linked_invoice_id,
        linked_trust_transaction_id=linked_trust_transaction_id,
        linked_payment_id=None,
        linked_expense_id=None,
        reversal_of_id=None,
        created_by_id=22,
        created_at=datetime.now(timezone.utc),
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )


def _transaction(
    *,
    txn_id: int = 11,
    transaction_type: str = "deposit",
    amount: str = "100.00",
    currency: str = "USD",
    client_id: int = 5,
    case_id: int = 9,
    trust_account_id: int = 1,
    ledger_id: int = 3,
    adjustment_direction: str | None = None,
):
    txn = TrustTransaction(
        id=txn_id,
        organization_id=7,
        trust_account_id=trust_account_id,
        ledger_id=ledger_id,
        client_id=client_id,
        case_id=case_id,
        linked_invoice_id=None,
        transaction_type=transaction_type,
        amount=Decimal(amount),
        currency=currency,
        description="Original trust transaction",
        payee_name="Payee" if transaction_type == "disbursement" else None,
        payee_type="third_party" if transaction_type == "disbursement" else None,
        payment_method="wire",
        reference_number="REF-1",
        adjustment_reason="fix" if transaction_type == "adjustment" else None,
        adjustment_direction=adjustment_direction,
        reversal_of_id=None,
        transaction_date=date(2026, 6, 17),
        created_by_id=22,
        created_at=datetime.now(timezone.utc),
        voided_at=None,
        voided_by_id=None,
        void_reason=None,
    )
    txn.receipt = None
    return txn


def test_validate_invoice_line_type_rejects_trust_categories():
    for forbidden in ["trust_deposit", "escrow", "property_funds", "invoice_retainer"]:
        with pytest.raises(HTTPException) as exc:
            validate_invoice_line_type(forbidden)
        assert exc.value.status_code == 400


def test_validate_invoice_line_type_maps_legacy_time_to_legal_fee():
    assert validate_invoice_line_type("time") == "hourly_work"


def test_derive_invoice_status_marks_overdue_only_when_balance_remains():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    invoice.due_date = date(2026, 6, 1)
    assert derive_invoice_status(invoice) == "overdue"
    invoice.paid_amount = Decimal("200.00")
    invoice.balance_due = Decimal("0.00")
    assert derive_invoice_status(invoice) == "paid"


def test_summarize_invoice_payment_method_handles_direct_trust_mixed_and_voided():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    assert summarize_invoice_payment_method(invoice) == "Not Paid"
    invoice.payments = [_payment(source="direct")]
    assert summarize_invoice_payment_method(invoice) == "Direct Payment"
    invoice.payments = [_payment(source="trust", linked_trust_transaction_id=11)]
    assert summarize_invoice_payment_method(invoice) == "Trust Applied"
    invoice.payments = [_payment(source="direct"), _payment(payment_id=41, source="trust", linked_trust_transaction_id=11)]
    assert summarize_invoice_payment_method(invoice) == "Mixed"
    voided = _payment(source="direct")
    voided.voided_at = datetime.now(timezone.utc)
    invoice.payments = [voided]
    assert summarize_invoice_payment_method(invoice) == "Voided/Reversed"


@pytest.mark.asyncio
async def test_trust_deposit_increases_balances_creates_receipt_and_not_operating_transaction():
    account = _trust_account("0.00")
    db = FinanceServiceDB(scalars=[account, _client(), _case(), None])

    txn, receipt, operating_txn = await create_trust_transaction(
        db,
        organization_id=7,
        trust_account_id=1,
        client_id=5,
        case_id=9,
        transaction_type="deposit",
        amount=Decimal("250.00"),
        currency="USD",
        transaction_date=date(2026, 6, 17),
        created_by_id=12,
        description="Initial retainer funding",
        payment_method="wire",
        reference_number="REF-100",
    )

    created_ledger = next(obj for obj in db.added if hasattr(obj, "current_balance") and obj is not account and not isinstance(obj, TrustTransaction))
    assert txn.transaction_type == "deposit"
    assert txn.reference_number == "TRX-2026-000100"
    assert txn.external_reference_number == "REF-100"
    assert receipt is not None
    assert isinstance(receipt, TrustReceipt)
    assert receipt.receipt_number == "TR-2026-000100"
    assert account.current_balance == Decimal("250.00")
    assert created_ledger.current_balance == Decimal("250.00")
    assert operating_txn is None
    assert not any(isinstance(obj, OperatingTransaction) for obj in db.added)


@pytest.mark.asyncio
async def test_disbursement_decreases_balances():
    account = _trust_account("400.00")
    ledger = _ledger("300.00")
    db = FinanceServiceDB(scalars=[account, _client(), _case(), ledger, Decimal("300.00"), Decimal("300.00")])

    txn, receipt, operating_txn = await create_trust_transaction(
        db,
        organization_id=7,
        trust_account_id=1,
        client_id=5,
        case_id=9,
        transaction_type="disbursement",
        amount=Decimal("100.00"),
        currency="USD",
        transaction_date=date(2026, 6, 17),
        created_by_id=12,
        description="Paid filing office",
        payee_name="Registrar General",
        payee_type="government",
        payment_method="cheque",
    )

    assert receipt is None
    assert txn.transaction_type == "disbursement"
    assert account.current_balance == Decimal("300.00")
    assert ledger.current_balance == Decimal("200.00")
    assert operating_txn is None
    assert not any(isinstance(obj, OperatingTransaction) for obj in db.added)


@pytest.mark.asyncio
async def test_manual_transfer_to_operating_is_blocked_outside_invoice_workflow():
    db = FinanceServiceDB(scalars=[_trust_account("400.00"), _client(), _case(), _ledger("300.00"), Decimal("300.00"), Decimal("300.00")])

    with pytest.raises(HTTPException) as exc:
        await create_trust_transaction(
            db,
            organization_id=7,
            trust_account_id=1,
            client_id=5,
            case_id=9,
            transaction_type="transfer_to_operating",
            amount=Decimal("100.00"),
            currency="USD",
            transaction_date=date(2026, 6, 17),
            created_by_id=12,
            description="Manual transfer should fail",
            linked_invoice_id=30,
        )
    assert exc.value.detail == "transfer_to_operating may only be generated from the invoice trust-application workflow"


@pytest.mark.asyncio
async def test_disbursement_blocked_if_insufficient_matter_balance():
    db = FinanceServiceDB(scalars=[_trust_account("400.00"), _client(), _case(), _ledger("50.00"), Decimal("50.00")])

    with pytest.raises(HTTPException) as exc:
        await create_trust_transaction(
            db,
            organization_id=7,
            trust_account_id=1,
            client_id=5,
            case_id=9,
            transaction_type="disbursement",
            amount=Decimal("100.00"),
            currency="USD",
            transaction_date=date(2026, 6, 17),
            created_by_id=12,
            description="Paid filing office",
            payee_name="Registrar General",
        )
    assert exc.value.detail == "Insufficient trust balance for this client/matter/currency."


@pytest.mark.asyncio
async def test_refund_decreases_balances_and_does_not_create_revenue():
    account = _trust_account("400.00")
    ledger = _ledger("200.00")
    db = FinanceServiceDB(scalars=[account, _client(), _case(), ledger, Decimal("200.00"), Decimal("200.00")])

    txn, receipt, operating_txn = await create_trust_transaction(
        db,
        organization_id=7,
        trust_account_id=1,
        client_id=5,
        case_id=9,
        transaction_type="refund",
        amount=Decimal("80.00"),
        currency="USD",
        transaction_date=date(2026, 6, 17),
        created_by_id=12,
        description="Returned unused retainer",
        payment_method="wire",
        reference_number="RF-22",
    )

    assert receipt is None
    assert txn.transaction_type == "refund"
    assert account.current_balance == Decimal("320.00")
    assert ledger.current_balance == Decimal("120.00")
    assert operating_txn is None
    assert not any(isinstance(obj, OperatingTransaction) for obj in db.added)


@pytest.mark.asyncio
async def test_refund_blocked_if_insufficient_balance():
    db = FinanceServiceDB(scalars=[_trust_account("400.00"), _client(), _case(), _ledger("20.00"), Decimal("20.00")])

    with pytest.raises(HTTPException) as exc:
        await create_trust_transaction(
            db,
            organization_id=7,
            trust_account_id=1,
            client_id=5,
            case_id=9,
            transaction_type="refund",
            amount=Decimal("80.00"),
            currency="USD",
            transaction_date=date(2026, 6, 17),
            created_by_id=12,
            description="Returned unused retainer",
        )
    assert exc.value.detail == "Insufficient trust balance for this client/matter/currency."


@pytest.mark.asyncio
async def test_adjustment_increase_increases_balances():
    account = _trust_account("300.00")
    ledger = _ledger("150.00")
    db = FinanceServiceDB(scalars=[account, _client(), _case(), ledger])

    txn, _, operating_txn = await create_trust_transaction(
        db,
        organization_id=7,
        trust_account_id=1,
        client_id=5,
        case_id=9,
        transaction_type="adjustment",
        amount=Decimal("25.00"),
        currency="USD",
        transaction_date=date(2026, 6, 17),
        created_by_id=12,
        description="Correct prior posting",
        adjustment_direction="increase",
        adjustment_reason="bank correction",
    )

    assert txn.adjustment_direction == "increase"
    assert account.current_balance == Decimal("325.00")
    assert ledger.current_balance == Decimal("175.00")
    assert operating_txn is None


@pytest.mark.asyncio
async def test_adjustment_decrease_decreases_balances_and_requires_sufficient_balance():
    account = _trust_account("300.00")
    ledger = _ledger("150.00")
    db = FinanceServiceDB(scalars=[account, _client(), _case(), ledger, Decimal("150.00"), Decimal("150.00")])

    txn, _, operating_txn = await create_trust_transaction(
        db,
        organization_id=7,
        trust_account_id=1,
        client_id=5,
        case_id=9,
        transaction_type="adjustment",
        amount=Decimal("25.00"),
        currency="USD",
        transaction_date=date(2026, 6, 17),
        created_by_id=12,
        description="Correct prior posting",
        adjustment_direction="decrease",
        adjustment_reason="bank correction",
    )

    assert txn.adjustment_direction == "decrease"
    assert account.current_balance == Decimal("275.00")
    assert ledger.current_balance == Decimal("125.00")
    assert operating_txn is None


@pytest.mark.asyncio
async def test_adjustment_requires_reason():
    with pytest.raises(HTTPException) as exc:
        await create_trust_transaction(
            FinanceServiceDB(scalars=[_trust_account("300.00"), _client(), _case(), _ledger("150.00")]),
            organization_id=7,
            trust_account_id=1,
            client_id=5,
            case_id=9,
            transaction_type="adjustment",
            amount=Decimal("25.00"),
            currency="USD",
            transaction_date=date(2026, 6, 17),
            created_by_id=12,
            description="Correct prior posting",
            adjustment_direction="increase",
            adjustment_reason="",
        )
    assert exc.value.detail == "adjustment_reason is required"


@pytest.mark.asyncio
async def test_void_deposit_creates_reversal_and_voids_receipt():
    original = _transaction(transaction_type="deposit")
    original.receipt = _receipt(transaction_id=original.id)
    account = _trust_account("100.00")
    ledger = _ledger("100.00")
    db = FinanceServiceDB(scalars=[original, account, _client(), _case(), ledger, Decimal("100.00"), Decimal("100.00")])

    voided, reversal = await void_trust_transaction(
        db,
        organization_id=7,
        transaction_id=original.id,
        void_reason="duplicate entry",
        voided_by_id=99,
    )

    assert voided.void_reason == "duplicate entry"
    assert voided.receipt.void_reason == "duplicate entry"
    assert reversal.transaction_type == "adjustment"
    assert reversal.adjustment_direction == "decrease"
    assert reversal.reversal_of_id == original.id
    assert reversal.adjustment_reason == REVERSAL_REASON
    assert account.current_balance == Decimal("0.00")
    assert ledger.current_balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_void_disbursement_creates_reversal_and_restores_balances():
    original = _transaction(transaction_type="disbursement")
    account = _trust_account("200.00")
    ledger = _ledger("50.00")
    db = FinanceServiceDB(scalars=[original, account, _client(), _case(), ledger])

    _, reversal = await void_trust_transaction(
        db,
        organization_id=7,
        transaction_id=original.id,
        void_reason="cheque voided",
        voided_by_id=99,
    )

    assert reversal.transaction_type == "adjustment"
    assert reversal.adjustment_direction == "increase"
    assert account.current_balance == Decimal("300.00")
    assert ledger.current_balance == Decimal("150.00")


@pytest.mark.asyncio
async def test_cannot_void_twice():
    original = _transaction(transaction_type="deposit")
    original.voided_at = datetime.now(timezone.utc)
    db = FinanceServiceDB(scalars=[original])

    with pytest.raises(HTTPException) as exc:
        await void_trust_transaction(
            db,
            organization_id=7,
            transaction_id=original.id,
            void_reason="duplicate entry",
            voided_by_id=99,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_void_deposit_blocked_if_reversal_would_create_negative_balance():
    original = _transaction(transaction_type="deposit")
    original.receipt = _receipt(transaction_id=original.id)
    db = FinanceServiceDB(scalars=[original, _trust_account("0.00"), _client(), _case(), _ledger("0.00"), Decimal("0.00")])

    with pytest.raises(HTTPException) as exc:
        await void_trust_transaction(
            db,
            organization_id=7,
            transaction_id=original.id,
            void_reason="duplicate entry",
            voided_by_id=99,
        )
    assert exc.value.detail == "Insufficient trust balance for this client/matter/currency."


@pytest.mark.asyncio
async def test_invoice_payment_void_direct_restores_invoice_and_creates_operating_reversal():
    invoice = _invoice(total="200.00", paid_amount="200.00", status="paid")
    payment = _payment(amount="200.00")
    original_operating = _operating_transaction(amount="200.00")
    operating_account = _operating_account("200.00")
    db = FinanceServiceDB(scalars=[payment, original_operating, operating_account, Decimal("0.00")])

    voided_payment, reversal_operating, reversal_trust = await void_invoice_payment(
        db,
        organization_id=7,
        invoice=invoice,
        payment_id=payment.id,
        void_reason="chargeback",
        voided_by_id=99,
        void_date=date(2026, 6, 18),
    )

    assert voided_payment.void_reason == "chargeback"
    assert invoice.paid_amount == Decimal("0.00")
    assert invoice.balance_due == Decimal("200.00")
    assert invoice.status == "sent"
    assert reversal_trust is None
    assert reversal_operating.transaction_type == "payment_reversal"
    assert reversal_operating.reversal_of_id == original_operating.id
    assert reversal_operating.linked_payment_id == payment.id
    assert original_operating.void_reason == "chargeback"
    assert operating_account.current_balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_invoice_payment_void_trust_restores_trust_and_creates_reversals():
    invoice = _invoice(total="200.00", paid_amount="200.00", status="paid")
    payment = _payment(source="trust", amount="200.00", linked_trust_transaction_id=11, linked_operating_transaction_id=70)
    original_operating = _operating_transaction(transaction_type="trust_transfer", amount="200.00", linked_trust_transaction_id=11)
    original_trust = _transaction(txn_id=11, transaction_type="transfer_to_operating", amount="200.00")
    operating_account = _operating_account("200.00")
    db = FinanceServiceDB(
        scalars=[
            payment,
            original_operating,
            original_trust,
            _trust_account("100.00"),
            _client(),
            _case(),
            invoice,
            _ledger("100.00"),
            operating_account,
            Decimal("0.00"),
        ]
    )

    voided_payment, reversal_operating, reversal_trust = await void_invoice_payment(
        db,
        organization_id=7,
        invoice=invoice,
        payment_id=payment.id,
        void_reason="invoice reopened",
        voided_by_id=99,
        void_date=date(2026, 6, 18),
    )

    assert voided_payment.void_reason == "invoice reopened"
    assert reversal_trust is not None
    assert reversal_trust.reversal_of_id == original_trust.id
    assert reversal_trust.adjustment_direction == "increase"
    assert reversal_trust.receipt is None
    assert reversal_operating.transaction_type == "payment_reversal"
    assert reversal_operating.reversal_of_id == original_operating.id
    assert reversal_operating.linked_trust_transaction_id == reversal_trust.id
    assert invoice.paid_amount == Decimal("0.00")
    assert invoice.balance_due == Decimal("200.00")
    assert invoice.status == "sent"
    assert original_trust.void_reason == "invoice reopened"
    assert operating_account.current_balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_invoice_payment_void_cannot_run_twice():
    invoice = _invoice(total="200.00", paid_amount="200.00", status="paid")
    payment = _payment(amount="200.00")
    payment.voided_at = datetime.now(timezone.utc)
    db = FinanceServiceDB(scalars=[payment])

    with pytest.raises(HTTPException) as exc:
        await void_invoice_payment(
            db,
            organization_id=7,
            invoice=invoice,
            payment_id=payment.id,
            void_reason="chargeback",
            voided_by_id=99,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_direct_payment_can_be_reapplied_after_void_without_overpaying():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    operating_account = _operating_account("0.00")
    db = FinanceServiceDB(scalars=[_client(), operating_account, operating_account])

    _, payment = await create_invoice_payment_operating_transaction(
        db,
        organization_id=7,
        invoice=invoice,
        created_by_id=12,
        transaction_date=date(2026, 6, 17),
    )
    payment_fetch = payment
    original_operating = next(obj for obj in db.added if isinstance(obj, OperatingTransaction) and obj.transaction_type == "invoice_payment")
    db.scalars.extend([payment_fetch, original_operating, operating_account, Decimal("0.00")])
    await void_invoice_payment(
        db,
        organization_id=7,
        invoice=invoice,
        payment_id=payment.id,
        void_reason="reopen",
        voided_by_id=99,
        void_date=date(2026, 6, 18),
    )

    assert invoice.balance_due == Decimal("200.00")

    db.scalars.extend([_client(), operating_account, operating_account])
    _, replacement_payment = await create_invoice_payment_operating_transaction(
        db,
        organization_id=7,
        invoice=invoice,
        created_by_id=12,
        transaction_date=date(2026, 6, 19),
    )
    assert replacement_payment.amount == Decimal("200.00")
    assert invoice.status == "paid"


@pytest.mark.asyncio
async def test_mixed_payments_can_void_one_without_corrupting_other():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    operating_account = _operating_account("0.00")
    db = FinanceServiceDB(
        scalars=[
            _trust_account("300.00"),
            _client(),
            _case(),
            invoice,
            _ledger("300.00"),
            Decimal("300.00"),
            Decimal("300.00"),
            operating_account,
            operating_account,
            _client(),
            operating_account,
            operating_account,
        ]
    )

    updated_invoice, trust_payment, _, _ = await apply_trust_to_invoice(
        db,
        organization_id=7,
        invoice=invoice,
        amount=Decimal("75.00"),
        created_by_id=12,
        trust_account_id=1,
        currency="USD",
        payment_date=date(2026, 6, 17),
    )
    _, direct_payment = await create_invoice_payment_operating_transaction(
        db,
        organization_id=7,
        invoice=updated_invoice,
        created_by_id=12,
        transaction_date=date(2026, 6, 18),
    )
    direct_operating = next(
        obj
        for obj in db.added
        if isinstance(obj, OperatingTransaction) and obj.transaction_type == "invoice_payment" and obj.linked_payment_id == direct_payment.id
    )
    db.scalars.extend([direct_payment, direct_operating, operating_account, Decimal("75.00")])
    await void_invoice_payment(
        db,
        organization_id=7,
        invoice=updated_invoice,
        payment_id=direct_payment.id,
        void_reason="returned payment",
        voided_by_id=99,
        void_date=date(2026, 6, 19),
    )

    assert updated_invoice.paid_amount == Decimal("75.00")
    assert updated_invoice.balance_due == Decimal("125.00")
    assert updated_invoice.status == "partially_paid"
    assert trust_payment.voided_at is None


@pytest.mark.asyncio
async def test_trust_endpoint_void_blocks_invoice_linked_transfer_to_operating():
    original = _transaction(txn_id=11, transaction_type="transfer_to_operating", amount="100.00")
    original.linked_invoice_id = 30
    db = FinanceServiceDB(scalars=[original])

    with pytest.raises(HTTPException) as exc:
        await void_trust_transaction(
            db,
            organization_id=7,
            transaction_id=original.id,
            void_reason="bad transfer",
            voided_by_id=99,
        )
    assert exc.value.detail == "Invoice-linked trust transfers must be voided through the invoice payment void workflow"


@pytest.mark.asyncio
async def test_trust_transaction_blocks_case_client_mismatch():
    db = FinanceServiceDB(scalars=[_trust_account("0.00"), _client(), _case(client_id=999)])

    with pytest.raises(HTTPException) as exc:
        await create_trust_transaction(
            db,
            organization_id=7,
            trust_account_id=1,
            client_id=5,
            case_id=9,
            transaction_type="deposit",
            amount=Decimal("250.00"),
            currency="USD",
            transaction_date=date(2026, 6, 17),
            created_by_id=12,
            description="Initial retainer funding",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Case/client mismatch"


@pytest.mark.asyncio
async def test_apply_trust_to_invoice_creates_transfer_operating_transaction_and_payment():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    operating_account = _operating_account("0.00")
    db = FinanceServiceDB(
        scalars=[
            _trust_account("300.00"),
            _client(),
            _case(),
            invoice,
            _ledger("300.00"),
            Decimal("300.00"),
            Decimal("300.00"),
            operating_account,
            operating_account,
        ]
    )

    updated_invoice, payment, trust_txn, operating_txn = await apply_trust_to_invoice(
        db,
        organization_id=7,
        invoice=invoice,
        amount=Decimal("200.00"),
        created_by_id=12,
        trust_account_id=1,
        currency="USD",
        payment_date=date(2026, 6, 17),
    )

    assert trust_txn.transaction_type == "transfer_to_operating"
    assert operating_txn.transaction_type == "trust_transfer"
    assert payment.payment_source == "trust"
    assert payment.linked_trust_transaction_id == trust_txn.id
    assert payment.linked_operating_transaction_id == operating_txn.id
    assert updated_invoice.paid_amount == Decimal("200.00")
    assert updated_invoice.balance_due == Decimal("0.00")
    assert updated_invoice.status == "paid"
    assert operating_account.current_balance == Decimal("200.00")


@pytest.mark.asyncio
async def test_apply_trust_to_invoice_partial_payment_marks_invoice_partially_paid():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    operating_account = _operating_account("0.00")
    db = FinanceServiceDB(
        scalars=[
            _trust_account("300.00"),
            _client(),
            _case(),
            invoice,
            _ledger("300.00"),
            Decimal("300.00"),
            Decimal("300.00"),
            operating_account,
            operating_account,
        ]
    )

    updated_invoice, payment, _, _ = await apply_trust_to_invoice(
        db,
        organization_id=7,
        invoice=invoice,
        amount=Decimal("75.00"),
        created_by_id=12,
        trust_account_id=1,
        currency="USD",
        payment_date=date(2026, 6, 17),
    )

    assert payment.amount == Decimal("75.00")
    assert updated_invoice.paid_amount == Decimal("75.00")
    assert updated_invoice.balance_due == Decimal("125.00")
    assert updated_invoice.status == "partially_paid"


@pytest.mark.asyncio
async def test_apply_trust_to_invoice_blocks_overpayment():
    invoice = _invoice(total="200.00", paid_amount="100.00", status="partially_paid")
    db = FinanceServiceDB(scalars=[])

    with pytest.raises(HTTPException) as exc:
        await apply_trust_to_invoice(
            db,
            organization_id=7,
            invoice=invoice,
            amount=Decimal("150.00"),
            created_by_id=12,
            trust_account_id=1,
            currency="USD",
        )
    assert exc.value.detail == "Amount cannot exceed invoice balance due"


@pytest.mark.asyncio
async def test_apply_trust_to_invoice_blocks_paid_invoice():
    invoice = _invoice(total="200.00", paid_amount="200.00", status="paid")
    db = FinanceServiceDB(scalars=[])

    with pytest.raises(HTTPException) as exc:
        await apply_trust_to_invoice(
            db,
            organization_id=7,
            invoice=invoice,
            amount=Decimal("10.00"),
            created_by_id=12,
            trust_account_id=1,
            currency="USD",
        )
    assert exc.value.detail == "Invoice is already fully paid"


@pytest.mark.asyncio
async def test_apply_trust_to_invoice_blocks_missing_case():
    invoice = _invoice(case_id=None, total="200.00", paid_amount="0.00", status="sent")
    db = FinanceServiceDB(scalars=[])

    with pytest.raises(HTTPException) as exc:
        await apply_trust_to_invoice(
            db,
            organization_id=7,
            invoice=invoice,
            amount=Decimal("10.00"),
            created_by_id=12,
            trust_account_id=1,
            currency="USD",
        )
    assert exc.value.detail == "Invoice must be linked to a matter to apply trust"


@pytest.mark.asyncio
async def test_direct_invoice_payment_creates_operating_transaction_and_payment_without_touching_trust():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    operating_account = _operating_account("0.00")
    db = FinanceServiceDB(scalars=[_client(), operating_account, operating_account])

    operating_txn, payment = await create_invoice_payment_operating_transaction(
        db,
        organization_id=7,
        invoice=invoice,
        created_by_id=12,
        transaction_date=date(2026, 6, 17),
    )

    assert operating_txn.transaction_type == "invoice_payment"
    assert payment.payment_source == "direct"
    assert payment.linked_trust_transaction_id is None
    assert invoice.paid_amount == Decimal("200.00")
    assert invoice.balance_due == Decimal("0.00")
    assert invoice.status == "paid"
    assert operating_account.current_balance == Decimal("200.00")


@pytest.mark.asyncio
async def test_direct_and_trust_mixed_payments_work():
    invoice = _invoice(total="200.00", paid_amount="0.00", status="sent")
    operating_account = _operating_account("0.00")
    db = FinanceServiceDB(
        scalars=[
            _trust_account("300.00"),
            _client(),
            _case(),
            invoice,
            _ledger("300.00"),
            Decimal("300.00"),
            Decimal("300.00"),
            operating_account,
            operating_account,
            _client(),
            operating_account,
            operating_account,
        ]
    )

    updated_invoice, trust_payment, _, _ = await apply_trust_to_invoice(
        db,
        organization_id=7,
        invoice=invoice,
        amount=Decimal("75.00"),
        created_by_id=12,
        trust_account_id=1,
        currency="USD",
        payment_date=date(2026, 6, 17),
    )
    _, direct_payment = await create_invoice_payment_operating_transaction(
        db,
        organization_id=7,
        invoice=updated_invoice,
        created_by_id=12,
        transaction_date=date(2026, 6, 18),
    )

    assert trust_payment.payment_source == "trust"
    assert direct_payment.payment_source == "direct"
    assert updated_invoice.paid_amount == Decimal("200.00")
    assert updated_invoice.balance_due == Decimal("0.00")
    assert updated_invoice.status == "paid"


@pytest.mark.asyncio
async def test_client_ledgers_group_balances_and_keep_currencies_separate():
    db = FinanceServiceDB(
        scalars=[],
        execute_rows=[[
            SimpleNamespace(client_id=5, client_name="Acme Ltd", currency="USD", balance=Decimal("150.00")),
            SimpleNamespace(client_id=5, client_name="Acme Ltd", currency="JMD", balance=Decimal("80.00")),
        ]],
    )

    rows = await get_client_ledgers(db, 7)

    assert rows == [
        {"client_id": 5, "client_name": "Acme Ltd", "currency": "USD", "balance": Decimal("150.00")},
        {"client_id": 5, "client_name": "Acme Ltd", "currency": "JMD", "balance": Decimal("80.00")},
    ]


@pytest.mark.asyncio
async def test_matter_ledgers_group_balances():
    db = FinanceServiceDB(
        scalars=[],
        execute_rows=[[
            SimpleNamespace(case_id=9, case_title="Smith Sale", client_id=5, client_name="Acme Ltd", currency="USD", balance=Decimal("150.00")),
        ]],
    )

    rows = await get_matter_ledgers(db, 7)

    assert rows == [
        {"case_id": 9, "case_title": "Smith Sale", "client_id": 5, "client_name": "Acme Ltd", "currency": "USD", "balance": Decimal("150.00")},
    ]


def test_apply_transaction_filters_excludes_voided_by_default():
    query = apply_transaction_filters(
        select(TrustTransaction),
        model=TrustTransaction,
        filters={"include_voided": False},
    )
    assert "voided_at IS NULL" in str(query)


def test_apply_transaction_filters_can_include_voided():
    query = apply_transaction_filters(
        select(TrustTransaction),
        model=TrustTransaction,
        filters={"include_voided": True},
    )
    assert "voided_at IS NULL" not in str(query)


@pytest.mark.asyncio
async def test_accounting_summary_uses_operating_transactions_only():
    db = AccountingSummaryDB(
        execute_rows=[
            [SimpleNamespace(currency="USD", total=Decimal("150.00"))],
            [SimpleNamespace(currency="USD", total=Decimal("650.00")), SimpleNamespace(currency="JMD", total=Decimal("1200.00"))],
            [
                SimpleNamespace(currency="USD", payment_source="direct", total=Decimal("500.00")),
                SimpleNamespace(currency="USD", payment_source="trust", total=Decimal("300.00")),
                SimpleNamespace(currency="JMD", payment_source="direct", total=Decimal("1200.00")),
            ],
            [SimpleNamespace(currency="USD", total=Decimal("120.00"))],
        ]
    )

    rows = await build_accounting_summary(db, 44)

    assert rows == [
        {"currency": "JMD", "revenue": Decimal("1200.00"), "expenses": Decimal("0.00"), "profit": Decimal("1200.00"), "operating_balance": Decimal("1200.00"), "direct_payment_total": Decimal("1200.00"), "trust_transfer_total": Decimal("0.00"), "tax_payable": Decimal("0.00")},
        {"currency": "USD", "revenue": Decimal("800.00"), "expenses": Decimal("150.00"), "profit": Decimal("650.00"), "operating_balance": Decimal("650.00"), "direct_payment_total": Decimal("500.00"), "trust_transfer_total": Decimal("300.00"), "tax_payable": Decimal("120.00")},
    ]


def test_accounting_summary_endpoint_excludes_trust_balances():
    user = DummyUser(id=2, organization_id=44, name="Lawyer", email="lawyer@example.com", role=UserRole.lawyer)
    db = AccountingSummaryDB(
        execute_rows=[
            [SimpleNamespace(currency="USD", total=Decimal("100.00"))],
            [SimpleNamespace(currency="USD", total=Decimal("400.00"))],
            [
                SimpleNamespace(currency="USD", payment_source="direct", total=Decimal("250.00")),
                SimpleNamespace(currency="USD", payment_source="trust", total=Decimal("250.00")),
            ],
            [SimpleNamespace(currency="USD", total=Decimal("50.00"))],
        ]
    )
    client = _override_client(user, db)

    try:
        res = client.get("/api/v1/accounting/summary")
        assert res.status_code == 200
        body = res.json()
        assert body["trust_funds_excluded"] is True
        assert body["currencies"][0]["currency"] == "USD"
        assert float(body["currencies"][0]["profit"]) == 400.0
        assert float(body["currencies"][0]["direct_payment_total"]) == 250.0
        assert float(body["currencies"][0]["trust_transfer_total"]) == 250.0
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_trust_transactions_requires_manage_role(client_for_user):
    client = client_for_user("paralegal")
    res = client.post(
        "/api/v1/trust/transactions",
        json={
            "trust_account_id": 1,
            "client_id": 3,
            "case_id": 7,
            "transaction_type": "deposit",
            "amount": "100.00",
            "currency": "USD",
            "description": "Seed deposit",
            "transaction_date": "2026-06-17",
        },
    )
    assert res.status_code == 403


def test_trust_void_requires_manage_role(client_for_user):
    client = client_for_user("lawyer")
    res = client.post("/api/v1/trust/transactions/1/void", json={"void_reason": "bad"})
    assert res.status_code == 403


def test_invoice_payment_void_requires_manage_role(client_for_user):
    client = client_for_user("lawyer")
    res = client.post("/api/v1/invoices/1/payments/1/void", json={"void_reason": "bad"})
    assert res.status_code == 403


def test_client_cannot_manage_accounting_endpoint(client_for_user):
    client = client_for_user("client")
    res = client.post("/api/v1/accounting/operating-accounts", json={"name": "Main", "currency": "USD"})
    assert res.status_code == 403


def test_direct_trust_transaction_edit_not_exposed(client_for_user):
    client = client_for_user("partner")
    res = client.patch("/api/v1/trust/transactions/101", json={"description": "edit"})
    assert res.status_code == 405
