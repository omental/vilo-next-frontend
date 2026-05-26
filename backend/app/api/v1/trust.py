from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.trust_account import TrustAccount
from app.models.trust_ledger import TrustLedger
from app.models.trust_transaction import TrustTransaction
from app.models.user import User
from app.schemas.trust import (
    TrustAccountCreate, TrustAccountResponse, TrustAdjustmentCreate,
    TrustApplyToInvoiceCreate, TrustLedgerResponse, TrustReceiptResponse,
    TrustReconciliationSummary, TrustTransactionResponse, TrustTxnCreate,
)
from app.services.audit import log_audit_event
from app.services.notifications import create_notification
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/trust", tags=["trust"])
MANAGE = ["partner", "admin"]
VIEW = ["partner", "admin", "lawyer", "paralegal"]
VALID_TXN_TYPES = {"deposit", "withdrawal", "refund", "disbursement", "adjustment", "applied_to_invoice"}


def acc_ser(a: TrustAccount) -> TrustAccountResponse:
    return TrustAccountResponse(**{k: getattr(a, k) for k in TrustAccountResponse.model_fields.keys()})


def led_ser(l: TrustLedger) -> TrustLedgerResponse:
    return TrustLedgerResponse(**{k: getattr(l, k) for k in TrustLedgerResponse.model_fields.keys()})


def txn_ser(t: TrustTransaction) -> TrustTransactionResponse:
    return TrustTransactionResponse(**{k: getattr(t, k) for k in TrustTransactionResponse.model_fields.keys()})


async def validate_links(db: AsyncSession, org_id: int, account_id: int, client_id: int, case_id: int | None, invoice_id: int | None = None):
    account = await db.scalar(select(TrustAccount).where(TrustAccount.id == account_id, TrustAccount.organization_id == org_id))
    if not account: raise HTTPException(status_code=400, detail="Trust account not found")
    client = await db.scalar(select(Client).where(Client.id == client_id, Client.organization_id == org_id))
    if not client: raise HTTPException(status_code=400, detail="Client not found")
    case = None
    if case_id is not None:
        case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == org_id))
        if not case: raise HTTPException(status_code=400, detail="Case not found")
        if case.client_id != client_id: raise HTTPException(status_code=400, detail="Case/client mismatch")
    invoice = None
    if invoice_id is not None:
        invoice = await db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == org_id))
        if not invoice: raise HTTPException(status_code=400, detail="Invoice not found")
        if invoice.client_id != client_id: raise HTTPException(status_code=400, detail="Invoice/client mismatch")
    return account, client, case, invoice


async def get_or_create_ledger(db: AsyncSession, org_id: int, account_id: int, client_id: int, case_id: int | None):
    ledger = await db.scalar(select(TrustLedger).where(
        TrustLedger.organization_id == org_id,
        TrustLedger.trust_account_id == account_id,
        TrustLedger.client_id == client_id,
        TrustLedger.case_id == case_id,
    ))
    if ledger:
        return ledger
    now = datetime.now(timezone.utc)
    ledger = TrustLedger(organization_id=org_id, trust_account_id=account_id, client_id=client_id, case_id=case_id, current_balance=Decimal("0"), created_at=now, updated_at=now)
    db.add(ledger); await db.flush()
    return ledger


async def create_transaction(db: AsyncSession, *, org_id: int, account_id: int, client_id: int, case_id: int | None, invoice_id: int | None, tx_type: str, amount: Decimal, description: str | None, tx_date: date, actor_id: int):
    if amount == 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    if tx_type not in VALID_TXN_TYPES:
        raise HTTPException(status_code=400, detail="Invalid transaction type")

    _, _, case, invoice = await validate_links(db, org_id, account_id, client_id, case_id, invoice_id)
    ledger = await get_or_create_ledger(db, org_id, account_id, client_id, case_id)

    delta = amount
    if tx_type in {"withdrawal", "refund", "disbursement", "applied_to_invoice"}:
        delta = -abs(amount)
    elif tx_type == "adjustment":
        delta = amount
    else:
        delta = abs(amount)
    if ledger.current_balance + delta < 0:
        raise HTTPException(status_code=400, detail="Insufficient trust balance")

    ledger.current_balance = ledger.current_balance + delta
    ledger.updated_at = datetime.now(timezone.utc)

    tx = TrustTransaction(
        organization_id=org_id, trust_account_id=account_id, ledger_id=ledger.id, client_id=client_id,
        case_id=case_id, invoice_id=invoice_id, transaction_type=tx_type, amount=amount,
        description=description, transaction_date=tx_date, created_by=actor_id, created_at=datetime.now(timezone.utc),
    )
    db.add(tx); await db.flush()

    if invoice is not None and tx_type == "applied_to_invoice":
        invoice.paid_amount = (invoice.paid_amount or Decimal("0")) + amount
        if invoice.paid_amount >= invoice.total:
            invoice.paid_amount = invoice.total
            invoice.balance_due = Decimal("0")
            invoice.status = "paid"
        else:
            invoice.balance_due = max(Decimal("0"), invoice.total - invoice.paid_amount)

    if case is not None:
        event_map = {
            "deposit": "trust_deposit_received",
            "refund": "trust_refund_issued",
            "disbursement": "trust_disbursement_recorded",
            "adjustment": "trust_adjustment_recorded",
            "applied_to_invoice": "trust_applied_to_invoice",
        }
        if tx_type in event_map:
            await create_case_timeline_event(
                db,
                organization_id=org_id,
                case_id=case.id,
                actor_id=actor_id,
                event_type=event_map[tx_type],
                title=f"Trust {tx_type} recorded",
                metadata_json={"trust_transaction_id": tx.id, "amount": str(amount), "invoice_id": invoice_id},
            )

    return tx


@router.get("/accounts", response_model=list[TrustAccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(VIEW))):
    rows = await db.scalars(select(TrustAccount).where(TrustAccount.organization_id == current_user.organization_id).order_by(TrustAccount.created_at.desc()))
    return [acc_ser(x) for x in rows.all()]


@router.post("/accounts", response_model=TrustAccountResponse)
async def create_account(payload: TrustAccountCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(MANAGE))):
    now = datetime.now(timezone.utc)
    obj = TrustAccount(organization_id=current_user.organization_id, created_at=now, updated_at=now, **payload.model_dump())
    db.add(obj); await db.commit(); await db.refresh(obj)
    return acc_ser(obj)


@router.get("/ledgers", response_model=list[TrustLedgerResponse])
async def list_ledgers(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(VIEW))):
    rows = await db.scalars(select(TrustLedger).where(TrustLedger.organization_id == current_user.organization_id).order_by(TrustLedger.updated_at.desc()))
    return [led_ser(x) for x in rows.all()]


@router.get("/transactions", response_model=list[TrustTransactionResponse])
async def list_transactions(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(VIEW))):
    rows = await db.scalars(select(TrustTransaction).where(TrustTransaction.organization_id == current_user.organization_id).order_by(TrustTransaction.created_at.desc()))
    return [txn_ser(x) for x in rows.all()]


@router.post("/deposit", response_model=TrustTransactionResponse)
async def deposit(payload: TrustTxnCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(MANAGE))):
    tx = await create_transaction(db, org_id=current_user.organization_id, account_id=payload.trust_account_id, client_id=payload.client_id, case_id=payload.case_id, invoice_id=None, tx_type="deposit", amount=payload.amount, description=payload.description, tx_date=payload.transaction_date, actor_id=current_user.id)
    await log_audit_event(
        db, organization_id=current_user.organization_id, user_id=current_user.id, action="trust_deposit",
        entity_type="trust_transaction", entity_id=str(tx.id), description="Trust deposit recorded",
        metadata_json={"client_id": tx.client_id, "case_id": tx.case_id, "amount": str(tx.amount)},
        ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"),
    )
    await db.commit(); await db.refresh(tx)
    return txn_ser(tx)


@router.post("/refund", response_model=TrustTransactionResponse)
async def refund(payload: TrustTxnCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(MANAGE))):
    tx = await create_transaction(db, org_id=current_user.organization_id, account_id=payload.trust_account_id, client_id=payload.client_id, case_id=payload.case_id, invoice_id=None, tx_type="refund", amount=payload.amount, description=payload.description, tx_date=payload.transaction_date, actor_id=current_user.id)
    await log_audit_event(
        db, organization_id=current_user.organization_id, user_id=current_user.id, action="trust_refund",
        entity_type="trust_transaction", entity_id=str(tx.id), description="Trust refund recorded",
        metadata_json={"client_id": tx.client_id, "case_id": tx.case_id, "amount": str(tx.amount)},
        ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"),
    )
    await db.commit(); await db.refresh(tx)
    return txn_ser(tx)


@router.post("/disbursement", response_model=TrustTransactionResponse)
async def disbursement(payload: TrustTxnCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(MANAGE))):
    tx = await create_transaction(db, org_id=current_user.organization_id, account_id=payload.trust_account_id, client_id=payload.client_id, case_id=payload.case_id, invoice_id=None, tx_type="disbursement", amount=payload.amount, description=payload.description, tx_date=payload.transaction_date, actor_id=current_user.id)
    await log_audit_event(
        db, organization_id=current_user.organization_id, user_id=current_user.id, action="trust_disbursement",
        entity_type="trust_transaction", entity_id=str(tx.id), description="Trust disbursement recorded",
        metadata_json={"client_id": tx.client_id, "case_id": tx.case_id, "amount": str(tx.amount)},
        ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"),
    )
    await db.commit(); await db.refresh(tx)
    return txn_ser(tx)


@router.post("/adjustment", response_model=TrustTransactionResponse)
async def adjustment(payload: TrustAdjustmentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(MANAGE))):
    direction = payload.direction.lower()
    if direction not in {"increase", "decrease"}:
        raise HTTPException(status_code=400, detail="direction must be increase or decrease")
    amount = payload.amount if direction == "increase" else -payload.amount
    tx = await create_transaction(db, org_id=current_user.organization_id, account_id=payload.trust_account_id, client_id=payload.client_id, case_id=payload.case_id, invoice_id=None, tx_type="adjustment", amount=amount, description=payload.description, tx_date=payload.transaction_date, actor_id=current_user.id)
    await db.commit(); await db.refresh(tx)
    return txn_ser(tx)


@router.post("/apply-to-invoice", response_model=TrustTransactionResponse)
async def apply_to_invoice(payload: TrustApplyToInvoiceCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(MANAGE))):
    tx = await create_transaction(db, org_id=current_user.organization_id, account_id=payload.trust_account_id, client_id=payload.client_id, case_id=payload.case_id, invoice_id=payload.invoice_id, tx_type="applied_to_invoice", amount=payload.amount, description=payload.description, tx_date=date.today(), actor_id=current_user.id)
    invoice = await db.scalar(select(Invoice).where(Invoice.id == payload.invoice_id, Invoice.organization_id == current_user.organization_id))
    if invoice and invoice.created_by != current_user.id:
        await create_notification(
            db,
            organization_id=current_user.organization_id,
            user_id=invoice.created_by,
            type="trust_applied",
            title=f"Trust applied to invoice {invoice.invoice_number}",
            body=f"{payload.amount} was applied from trust to this invoice.",
            metadata_json={"invoice_id": invoice.id, "trust_transaction_id": tx.id},
        )
    await log_audit_event(
        db, organization_id=current_user.organization_id, user_id=current_user.id, action="trust_applied",
        entity_type="trust_transaction", entity_id=str(tx.id), description="Trust applied to invoice",
        metadata_json={"invoice_id": payload.invoice_id, "client_id": payload.client_id, "amount": str(payload.amount)},
        ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"),
    )
    await db.commit(); await db.refresh(tx)
    return txn_ser(tx)


@router.get("/transactions/{transaction_id}/receipt", response_model=TrustReceiptResponse)
async def receipt(transaction_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(VIEW))):
    tx = await db.scalar(select(TrustTransaction).where(TrustTransaction.id == transaction_id, TrustTransaction.organization_id == current_user.organization_id))
    if not tx: raise HTTPException(status_code=404, detail="Transaction not found")
    return TrustReceiptResponse(receipt_number=f"TR-{datetime.now().year}-{tx.id:06d}", client=tx.client_id, case=tx.case_id, amount=tx.amount, date=tx.transaction_date, description=tx.description, trust_account=tx.trust_account_id)


@router.get("/reconciliation-summary", response_model=TrustReconciliationSummary)
async def reconcile_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(VIEW))):
    total_bal = Decimal(str((await db.scalar(select(func.coalesce(func.sum(TrustLedger.current_balance), 0)).where(TrustLedger.organization_id == current_user.organization_id))) or 0))
    client_bal = Decimal(str((await db.scalar(select(func.coalesce(func.sum(TrustLedger.current_balance), 0)).where(TrustLedger.organization_id == current_user.organization_id))) or 0))
    case_bal = Decimal(str((await db.scalar(select(func.coalesce(func.sum(TrustLedger.current_balance), 0)).where(TrustLedger.organization_id == current_user.organization_id, TrustLedger.case_id.is_not(None)))) or 0))
    return TrustReconciliationSummary(total_trust_account_balance=total_bal, total_client_ledger_balances=client_bal, total_matter_case_balances=case_bal, matches=(total_bal == client_bal))
