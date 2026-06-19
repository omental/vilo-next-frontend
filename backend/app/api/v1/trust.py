from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.trust_account import TrustAccount
from app.models.trust_receipt import TrustReceipt
from app.models.trust_transaction import TrustTransaction
from app.models.user import User
from app.schemas.trust import (
    TrustAccountCreate,
    TrustAccountResponse,
    TrustBalanceResponse,
    TrustClientLedgerRow,
    TrustMatterLedgerRow,
    TrustReceiptResponse,
    TrustTransactionCreate,
    TrustTransactionReverseRequest,
    TrustTransactionResponse,
    TrustReferenceSummary,
    TrustReceiptLink,
    TrustReverseResponse,
)
from app.services.finance import (
    apply_transaction_filters,
    create_trust_transaction,
    generate_trust_reference_number,
    get_client_ledgers,
    get_client_trust_balance,
    get_matter_ledgers,
    get_matter_trust_balance,
    get_or_create_default_trust_account,
    get_trust_account_balance,
    get_trust_transaction_status,
    log_finance_guardrail_event,
    money,
    normalize_currency,
    void_trust_transaction,
)
from app.services.pdf import generate_trust_receipt_pdf

router = APIRouter(prefix="/trust", tags=["trust"])
MANAGE = ["partner", "admin"]
VIEW = ["partner", "admin", "lawyer", "paralegal"]


def serialize_account(account: TrustAccount) -> TrustAccountResponse:
    return TrustAccountResponse(**{field: getattr(account, field) for field in TrustAccountResponse.model_fields.keys()})


def serialize_transaction(transaction: TrustTransaction, *, running_balance=None) -> TrustTransactionResponse:
    reversal_txn = None
    if getattr(transaction, "reversal_transactions", None):
        reversal = sorted(transaction.reversal_transactions, key=lambda row: row.id)[0]
        reversal_txn = TrustReferenceSummary(id=reversal.id, reference_number=reversal.reference_number)
    reversal_of_txn = None
    if getattr(transaction, "reversal_of", None):
        reversal_of_txn = TrustReferenceSummary(id=transaction.reversal_of.id, reference_number=transaction.reversal_of.reference_number)
    receipt = getattr(transaction, "receipt", None)
    return TrustTransactionResponse(
        id=transaction.id,
        organization_id=transaction.organization_id,
        trust_account_id=transaction.trust_account_id,
        ledger_id=transaction.ledger_id,
        client_id=transaction.client_id,
        case_id=transaction.case_id,
        linked_invoice_id=transaction.linked_invoice_id,
        linked_invoice_number=getattr(getattr(transaction, "invoice", None), "invoice_number", None),
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        currency=transaction.currency,
        transaction_date=transaction.transaction_date,
        description=transaction.description,
        payee_name=transaction.payee_name,
        payee_type=transaction.payee_type,
        payment_method=transaction.payment_method,
        reference_number=transaction.reference_number,
        external_reference_number=getattr(transaction, "external_reference_number", None),
        adjustment_reason=transaction.adjustment_reason,
        adjustment_direction=transaction.adjustment_direction,
        reversal_of_id=transaction.reversal_of_id,
        created_by_id=transaction.created_by_id,
        created_by_name=getattr(getattr(transaction, "creator", None), "name", None),
        created_at=transaction.created_at,
        voided_at=transaction.voided_at,
        voided_by_id=transaction.voided_by_id,
        voided_by_name=getattr(getattr(transaction, "voided_by", None), "name", None),
        void_reason=transaction.void_reason,
        status=get_trust_transaction_status(transaction),
        client_name=getattr(getattr(transaction, "client", None), "name", None),
        case_title=getattr(getattr(transaction, "case", None), "title", None),
        trust_account_name=getattr(getattr(transaction, "trust_account", None), "name", None),
        running_balance=running_balance,
        receipt=(
            TrustReceiptLink(id=receipt.id, receipt_number=receipt.receipt_number, pdf_available=bool(receipt.pdf_path))
            if receipt is not None else None
        ),
        reversal_transaction=reversal_txn,
        reversal_of_transaction=reversal_of_txn,
    )


def serialize_receipt(receipt: TrustReceipt) -> TrustReceiptResponse:
    return TrustReceiptResponse(
        id=receipt.id,
        receipt_number=receipt.receipt_number,
        trust_transaction_id=receipt.trust_transaction_id,
        client_id=receipt.client_id,
        case_id=receipt.case_id,
        amount=receipt.amount,
        currency=receipt.currency,
        payment_method=receipt.payment_method,
        description=receipt.description,
        reference_number=getattr(getattr(receipt, "trust_transaction", None), "reference_number", None),
        external_reference_number=getattr(getattr(receipt, "trust_transaction", None), "external_reference_number", None),
        issued_at=receipt.issued_at,
        issued_by_id=receipt.issued_by_id,
        issued_by_name=getattr(getattr(receipt, "issued_by", None), "name", None),
        pdf_available=bool(receipt.pdf_path),
        voided_at=receipt.voided_at,
        voided_by_id=receipt.voided_by_id,
        voided_by_name=getattr(getattr(receipt, "voided_by", None), "name", None),
        void_reason=receipt.void_reason,
    )


def transaction_load_options():
    return (
        selectinload(TrustTransaction.client),
        selectinload(TrustTransaction.case),
        selectinload(TrustTransaction.invoice),
        selectinload(TrustTransaction.creator),
        selectinload(TrustTransaction.voided_by),
        selectinload(TrustTransaction.receipt),
        selectinload(TrustTransaction.trust_account),
        selectinload(TrustTransaction.reversal_transactions),
        selectinload(TrustTransaction.reversal_of),
    )


def _transaction_delta(transaction: TrustTransaction):
    if transaction.transaction_type == "deposit":
        return money(transaction.amount)
    if transaction.transaction_type == "adjustment":
        return money(-transaction.amount if transaction.adjustment_direction == "decrease" else transaction.amount)
    return money(-transaction.amount)


def attach_running_balances(transactions: list[TrustTransaction]) -> dict[int, object]:
    balances = {}
    running = {}
    for txn in sorted(transactions, key=lambda row: (row.transaction_date, row.created_at, row.id)):
        key = (txn.client_id, txn.case_id, txn.currency)
        running[key] = money(running.get(key, 0) + _transaction_delta(txn))
        balances[txn.id] = running[key]
    return balances


def _audit_request(request: Request) -> dict:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


@router.get("/accounts", response_model=list[TrustAccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    rows = await db.scalars(
        select(TrustAccount)
        .where(TrustAccount.organization_id == current_user.organization_id)
        .order_by(TrustAccount.currency.asc(), TrustAccount.name.asc())
    )
    return [serialize_account(row) for row in rows.all()]


@router.post("/accounts", response_model=TrustAccountResponse)
async def create_account(
    payload: TrustAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    now = datetime.now(timezone.utc)
    account = TrustAccount(
        organization_id=current_user.organization_id,
        name=payload.name,
        currency=payload.currency,
        account_type=payload.account_type,
        is_default=payload.is_default,
        opening_balance=money(payload.opening_balance),
        current_balance=money(payload.opening_balance),
        is_active=True,
        bank_name=payload.bank_name,
        account_number_last4=payload.account_number_last4,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return serialize_account(account)


@router.get("/balances", response_model=TrustBalanceResponse)
async def get_balances(
    client_id: int | None = Query(default=None),
    case_id: int | None = Query(default=None),
    currency: str = Query(default="JMD"),
    trust_account_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    resolved_currency = normalize_currency(currency)
    return TrustBalanceResponse(
        trust_account_id=trust_account_id,
        client_id=client_id,
        case_id=case_id,
        trust_account_balance=(
            await get_trust_account_balance(db, current_user.organization_id, trust_account_id, resolved_currency)
            if trust_account_id is not None
            else None
        ),
        client_balance=(
            await get_client_trust_balance(db, current_user.organization_id, client_id, resolved_currency)
            if client_id is not None
            else None
        ),
        matter_balance=(
            await get_matter_trust_balance(db, current_user.organization_id, case_id, resolved_currency)
            if case_id is not None
            else None
        ),
        currency=resolved_currency,
        as_of=datetime.now(timezone.utc),
    )


@router.get("/client-ledgers", response_model=list[TrustClientLedgerRow])
async def client_ledgers(
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    return [TrustClientLedgerRow(**row) for row in await get_client_ledgers(db, current_user.organization_id, currency)]


@router.get("/matter-ledgers", response_model=list[TrustMatterLedgerRow])
async def matter_ledgers(
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    return [TrustMatterLedgerRow(**row) for row in await get_matter_ledgers(db, current_user.organization_id, currency)]


@router.get("/transactions", response_model=list[TrustTransactionResponse])
async def list_transactions(
    client_id: int | None = Query(default=None),
    case_id: int | None = Query(default=None),
    trust_account_id: int | None = Query(default=None),
    transaction_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    include_voided: bool = Query(default=False),
    include_reversed: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    query = (
        select(TrustTransaction)
        .where(TrustTransaction.organization_id == current_user.organization_id)
        .options(*transaction_load_options())
    )
    query = apply_transaction_filters(
        query,
        model=TrustTransaction,
        filters={
            "client_id": client_id,
            "case_id": case_id,
            "trust_account_id": trust_account_id,
            "transaction_type": transaction_type,
            "status": status,
            "currency": currency,
            "date_from": date_from,
            "date_to": date_to,
            "include_voided": include_voided,
            "include_reversed": include_reversed,
        },
    )
    rows = (await db.scalars(query.order_by(TrustTransaction.transaction_date.asc(), TrustTransaction.created_at.asc(), TrustTransaction.id.asc()))).all()
    running_balances = attach_running_balances(rows)
    return [serialize_transaction(row, running_balance=running_balances.get(row.id)) for row in rows]


@router.post("/transactions", response_model=TrustTransactionResponse)
async def create_transaction(
    payload: TrustTransactionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    if payload.transaction_type == "transfer_to_operating":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="transfer_to_operating is reserved for Phase C invoice-linked workflow",
        )
    try:
        txn, _, _ = await create_trust_transaction(
            db,
            organization_id=current_user.organization_id,
            trust_account_id=payload.trust_account_id,
            client_id=payload.client_id,
            case_id=payload.case_id,
            transaction_type=payload.transaction_type,
            amount=payload.amount,
            currency=payload.currency,
            transaction_date=payload.transaction_date,
            created_by_id=current_user.id,
            description=payload.description,
            payee_name=payload.payee_name,
            payee_type=payload.payee_type,
            payment_method=payload.payment_method,
            external_reference_number=payload.external_reference_number,
            adjustment_direction=payload.adjustment_direction,
            adjustment_reason=payload.adjustment_reason,
            audit_request=_audit_request(request),
        )
    except HTTPException as exc:
        if exc.detail == "Insufficient trust balance for this client/matter/currency.":
            await log_finance_guardrail_event(
                db,
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                action="trust_negative_balance_blocked",
                detail="Blocked trust outflow due to insufficient balance",
                client_id=payload.client_id,
                case_id=payload.case_id,
            )
            await db.commit()
        raise
    await db.commit()
    refreshed = await db.scalar(
        select(TrustTransaction)
        .where(TrustTransaction.id == txn.id, TrustTransaction.organization_id == current_user.organization_id)
        .options(*transaction_load_options())
    )
    return serialize_transaction(refreshed or txn)


@router.get("/transactions/{transaction_id}", response_model=TrustTransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    transaction = await db.scalar(
        select(TrustTransaction)
        .where(
            TrustTransaction.id == transaction_id,
            TrustTransaction.organization_id == current_user.organization_id,
        )
        .options(*transaction_load_options())
    )
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust transaction not found")
    cohort = (
        await db.scalars(
            select(TrustTransaction)
            .where(
                TrustTransaction.organization_id == current_user.organization_id,
                TrustTransaction.client_id == transaction.client_id,
                TrustTransaction.case_id == transaction.case_id,
                TrustTransaction.currency == transaction.currency,
            )
            .order_by(TrustTransaction.transaction_date.asc(), TrustTransaction.created_at.asc(), TrustTransaction.id.asc())
        )
    ).all()
    running_balances = attach_running_balances(cohort)
    return serialize_transaction(transaction, running_balance=running_balances.get(transaction.id))


async def _reverse_transaction(
    transaction_id: int,
    payload: TrustTransactionReverseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    try:
        original, reversal = await void_trust_transaction(
            db,
            organization_id=current_user.organization_id,
            transaction_id=transaction_id,
            void_reason=payload.reversal_reason,
            voided_by_id=current_user.id,
            audit_request=_audit_request(request),
        )
    except HTTPException as exc:
        if exc.detail == "Insufficient trust balance for this client/matter/currency.":
            await log_finance_guardrail_event(
                db,
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                action="trust_reverse_negative_balance_blocked",
                detail="Blocked trust reversal because the reversal entry would create a negative balance",
                client_id=None,
                case_id=None,
            )
            await db.commit()
        raise
    await db.commit()
    reloaded = (
        await db.scalars(
            select(TrustTransaction)
            .where(
                TrustTransaction.organization_id == current_user.organization_id,
                TrustTransaction.id.in_([original.id, reversal.id]),
            )
            .options(*transaction_load_options())
            .order_by(TrustTransaction.id.asc())
        )
    ).all()
    by_id = {row.id: row for row in reloaded}
    return TrustReverseResponse(
        original_transaction=serialize_transaction(by_id.get(original.id, original)),
        reversal_transaction=serialize_transaction(by_id.get(reversal.id, reversal)),
    )


@router.post("/transactions/{transaction_id}/reverse", response_model=TrustReverseResponse)
async def reverse_transaction(
    transaction_id: int,
    payload: TrustTransactionReverseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    return await _reverse_transaction(transaction_id=transaction_id, payload=payload, request=request, db=db, current_user=current_user)


@router.post("/transactions/{transaction_id}/void", response_model=TrustReverseResponse)
async def void_transaction(
    transaction_id: int,
    payload: TrustTransactionReverseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    return await _reverse_transaction(transaction_id=transaction_id, payload=payload, request=request, db=db, current_user=current_user)


@router.get("/receipts", response_model=list[TrustReceiptResponse])
async def list_receipts(
    client_id: int | None = Query(default=None),
    case_id: int | None = Query(default=None),
    currency: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    query = (
        select(TrustReceipt)
        .join(TrustTransaction, TrustTransaction.id == TrustReceipt.trust_transaction_id)
        .where(TrustReceipt.organization_id == current_user.organization_id)
        .options(
            selectinload(TrustReceipt.trust_transaction),
            selectinload(TrustReceipt.issued_by),
            selectinload(TrustReceipt.voided_by),
        )
        .order_by(TrustReceipt.issued_at.desc(), TrustReceipt.id.desc())
    )
    if client_id is not None:
        query = query.where(TrustReceipt.client_id == client_id)
    if case_id is not None:
        query = query.where(TrustReceipt.case_id == case_id)
    if currency is not None:
        query = query.where(TrustReceipt.currency == normalize_currency(currency))
    if date_from is not None:
        query = query.where(TrustTransaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.where(TrustTransaction.transaction_date <= date_to)
    return [serialize_receipt(row) for row in (await db.scalars(query)).all()]


@router.get("/receipts/{receipt_id}", response_model=TrustReceiptResponse)
async def get_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    receipt = await db.scalar(
        select(TrustReceipt)
        .where(
            TrustReceipt.id == receipt_id,
            TrustReceipt.organization_id == current_user.organization_id,
        )
        .options(
            selectinload(TrustReceipt.trust_transaction),
            selectinload(TrustReceipt.issued_by),
            selectinload(TrustReceipt.voided_by),
        )
    )
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust receipt not found")
    return serialize_receipt(receipt)


@router.get("/receipts/{receipt_id}/download")
async def download_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    receipt = await db.scalar(
        select(TrustReceipt).where(
            TrustReceipt.id == receipt_id,
            TrustReceipt.organization_id == current_user.organization_id,
        )
    )
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust receipt not found")
    if not receipt.pdf_path:
        generated = await generate_trust_receipt_pdf(receipt.id, db=db, organization_id=current_user.organization_id)
        receipt.pdf_path = str(generated.file_path)
        await db.commit()
    file_path = Path(receipt.pdf_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust receipt file not found")
    return FileResponse(path=str(file_path), filename=f"{receipt.receipt_number}.pdf", media_type="application/pdf")


@router.post("/deposit", response_model=TrustTransactionResponse)
async def legacy_deposit(
    payload: TrustTransactionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    deposit_payload = payload.model_copy(update={"transaction_type": "deposit"})
    return await create_transaction(deposit_payload, request=request, db=db, current_user=current_user)


@router.post("/accounts/default/{currency}", response_model=TrustAccountResponse)
async def create_or_get_default_account(
    currency: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    account = await get_or_create_default_trust_account(db, current_user.organization_id, currency)
    await db.commit()
    await db.refresh(account)
    return serialize_account(account)
