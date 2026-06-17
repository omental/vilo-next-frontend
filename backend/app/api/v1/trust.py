from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    TrustTransactionResponse,
    TrustTransactionVoidRequest,
    TrustVoidResponse,
)
from app.services.finance import (
    apply_transaction_filters,
    create_trust_transaction,
    get_client_ledgers,
    get_client_trust_balance,
    get_matter_ledgers,
    get_matter_trust_balance,
    get_or_create_default_trust_account,
    get_trust_account_balance,
    log_finance_guardrail_event,
    money,
    normalize_currency,
    void_trust_transaction,
)

router = APIRouter(prefix="/trust", tags=["trust"])
MANAGE = ["partner", "admin"]
VIEW = ["partner", "admin", "lawyer", "paralegal"]


def serialize_account(account: TrustAccount) -> TrustAccountResponse:
    return TrustAccountResponse(**{field: getattr(account, field) for field in TrustAccountResponse.model_fields.keys()})


def serialize_transaction(transaction: TrustTransaction) -> TrustTransactionResponse:
    payload = {field: getattr(transaction, field) for field in TrustTransactionResponse.model_fields.keys() if field != "receipt_id"}
    payload["receipt_id"] = getattr(transaction.__dict__.get("receipt"), "id", None)
    return TrustTransactionResponse(**payload)


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
        issued_at=receipt.issued_at,
        issued_by_id=receipt.issued_by_id,
        pdf_available=bool(receipt.pdf_path),
        voided_at=receipt.voided_at,
        voided_by_id=receipt.voided_by_id,
        void_reason=receipt.void_reason,
    )


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
    currency: str = Query(default="USD"),
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
    currency: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    include_voided: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    query = select(TrustTransaction).where(TrustTransaction.organization_id == current_user.organization_id)
    query = apply_transaction_filters(
        query,
        model=TrustTransaction,
        filters={
            "client_id": client_id,
            "case_id": case_id,
            "trust_account_id": trust_account_id,
            "transaction_type": transaction_type,
            "currency": currency,
            "date_from": date_from,
            "date_to": date_to,
            "include_voided": include_voided,
        },
    )
    rows = await db.scalars(query.order_by(TrustTransaction.created_at.desc(), TrustTransaction.id.desc()))
    return [serialize_transaction(row) for row in rows.all()]


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
            reference_number=payload.reference_number,
            adjustment_direction=payload.adjustment_direction,
            adjustment_reason=payload.adjustment_reason,
            audit_request=_audit_request(request),
        )
    except HTTPException as exc:
        if exc.detail in {"Insufficient matter trust balance", "Insufficient client trust balance"}:
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
    await db.refresh(txn)
    return serialize_transaction(txn)


@router.post("/transactions/{transaction_id}/void", response_model=TrustVoidResponse)
async def void_transaction(
    transaction_id: int,
    payload: TrustTransactionVoidRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    try:
        original, reversal = await void_trust_transaction(
            db,
            organization_id=current_user.organization_id,
            transaction_id=transaction_id,
            void_reason=payload.void_reason,
            voided_by_id=current_user.id,
            audit_request=_audit_request(request),
        )
    except HTTPException as exc:
        if exc.detail in {"Insufficient matter trust balance", "Insufficient client trust balance"}:
            await log_finance_guardrail_event(
                db,
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                action="trust_void_negative_balance_blocked",
                detail="Blocked trust void because reversal would create negative balance",
                client_id=None,
                case_id=None,
            )
            await db.commit()
        raise
    await db.commit()
    await db.refresh(original)
    await db.refresh(reversal)
    return TrustVoidResponse(
        original_transaction=serialize_transaction(original),
        reversal_transaction=serialize_transaction(reversal),
    )


@router.get("/receipts/{receipt_id}", response_model=TrustReceiptResponse)
async def get_receipt(
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
    return serialize_receipt(receipt)


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
