from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.billing_rate import BillingRate
from app.models.firm_payment_account import FirmPaymentAccount
from app.models.organization import Organization
from app.models.user import User
from app.schemas.billing import (
    BillingTaxSettingsResponse,
    BillingTaxSettingsUpdate,
    BillingRateCreate,
    BillingRateResponse,
    BillingRateUpdate,
    EffectiveBillingRateResponse,
    FirmPaymentAccountCreate,
    FirmPaymentAccountResponse,
    FirmPaymentAccountUpdate,
)
from app.services.billing import (
    clear_default_payment_accounts,
    get_effective_hourly_rate,
    validate_billing_rate_payload,
)
from app.services.finance import money, normalize_currency, utc_now

router = APIRouter(prefix="/settings", tags=["settings"])
MANAGE = ["partner", "admin"]
VIEW = ["partner", "admin", "lawyer", "paralegal"]


def serialize_payment_account(account: FirmPaymentAccount) -> FirmPaymentAccountResponse:
    return FirmPaymentAccountResponse(**{field: getattr(account, field) for field in FirmPaymentAccountResponse.model_fields.keys()})


def serialize_billing_rate(rate: BillingRate) -> BillingRateResponse:
    return BillingRateResponse(**{field: getattr(rate, field) for field in BillingRateResponse.model_fields.keys()})


def serialize_billing_tax_settings(organization: Organization | None) -> BillingTaxSettingsResponse:
    return BillingTaxSettingsResponse(
        invoice_tax_label=getattr(organization, "invoice_tax_label", None) or "GCT",
        invoice_tax_rate=money((getattr(organization, "invoice_tax_rate", 0) or 0)),
    )


@router.get("/billing-tax", response_model=BillingTaxSettingsResponse)
async def get_billing_tax_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    organization = await db.scalar(select(Organization).where(Organization.id == current_user.organization_id))
    return serialize_billing_tax_settings(organization)


@router.patch("/billing-tax", response_model=BillingTaxSettingsResponse)
async def update_billing_tax_settings(
    payload: BillingTaxSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    organization = await db.scalar(select(Organization).where(Organization.id == current_user.organization_id))
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization.invoice_tax_label = payload.invoice_tax_label.strip()
    organization.invoice_tax_rate = money(payload.invoice_tax_rate)
    await db.commit()
    return serialize_billing_tax_settings(organization)


@router.get("/payment-accounts", response_model=list[FirmPaymentAccountResponse])
async def list_payment_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    rows = await db.scalars(
        select(FirmPaymentAccount)
        .where(FirmPaymentAccount.organization_id == current_user.organization_id)
        .order_by(FirmPaymentAccount.currency.asc(), FirmPaymentAccount.account_name.asc())
    )
    return [serialize_payment_account(row) for row in rows.all()]


@router.post("/payment-accounts", response_model=FirmPaymentAccountResponse)
async def create_payment_account(
    payload: FirmPaymentAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    now = utc_now()
    if payload.is_default:
        await clear_default_payment_accounts(
            db,
            organization_id=current_user.organization_id,
            currency=payload.currency,
        )
    account = FirmPaymentAccount(
        organization_id=current_user.organization_id,
        account_name=payload.account_name.strip(),
        bank_name=payload.bank_name.strip(),
        account_number=payload.account_number.strip(),
        currency=payload.currency,
        swift_routing=(payload.swift_routing or None),
        notes=(payload.notes or None),
        payment_instructions=(payload.payment_instructions or None),
        is_default=payload.is_default,
        is_active=True,
        created_by_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return serialize_payment_account(account)


@router.patch("/payment-accounts/{account_id}", response_model=FirmPaymentAccountResponse)
async def update_payment_account(
    account_id: int,
    payload: FirmPaymentAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    account = await db.scalar(
        select(FirmPaymentAccount).where(
            FirmPaymentAccount.id == account_id,
            FirmPaymentAccount.organization_id == current_user.organization_id,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment account not found")

    updates = payload.model_dump(exclude_unset=True)
    next_currency = updates.get("currency", account.currency)
    if updates.get("is_default") is True:
        await clear_default_payment_accounts(
            db,
            organization_id=current_user.organization_id,
            currency=next_currency,
            exclude_account_id=account.id,
        )
    for key, value in updates.items():
        setattr(account, key, value)
    account.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(account)
    return serialize_payment_account(account)


@router.post("/payment-accounts/{account_id}/set-default", response_model=FirmPaymentAccountResponse)
async def set_default_payment_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    account = await db.scalar(
        select(FirmPaymentAccount).where(
            FirmPaymentAccount.id == account_id,
            FirmPaymentAccount.organization_id == current_user.organization_id,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment account not found")
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive payment accounts cannot be default")

    await clear_default_payment_accounts(
        db,
        organization_id=current_user.organization_id,
        currency=account.currency,
        exclude_account_id=account.id,
    )
    account.is_default = True
    account.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(account)
    return serialize_payment_account(account)


@router.delete("/payment-accounts/{account_id}")
async def deactivate_payment_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    account = await db.scalar(
        select(FirmPaymentAccount).where(
            FirmPaymentAccount.id == account_id,
            FirmPaymentAccount.organization_id == current_user.organization_id,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment account not found")
    account.is_active = False
    account.is_default = False
    account.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.get("/billing-rates", response_model=list[BillingRateResponse])
async def list_billing_rates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    rows = await db.scalars(
        select(BillingRate)
        .where(BillingRate.organization_id == current_user.organization_id)
        .order_by(BillingRate.rate_type.asc(), BillingRate.currency.asc(), BillingRate.id.asc())
    )
    return [serialize_billing_rate(row) for row in rows.all()]


@router.post("/billing-rates", response_model=BillingRateResponse)
async def create_billing_rate(
    payload: BillingRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    role_name, user_id = await validate_billing_rate_payload(
        db,
        organization_id=current_user.organization_id,
        rate_type=payload.rate_type,
        role_name=payload.role_name,
        user_id=payload.user_id,
    )
    now = utc_now()
    rate = BillingRate(
        organization_id=current_user.organization_id,
        rate_type=payload.rate_type.strip().lower(),
        role_name=role_name,
        user_id=user_id,
        currency=payload.currency,
        hourly_rate=money(payload.hourly_rate),
        is_active=payload.is_active,
        created_by_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return serialize_billing_rate(rate)


@router.patch("/billing-rates/{rate_id}", response_model=BillingRateResponse)
async def update_billing_rate(
    rate_id: int,
    payload: BillingRateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    rate = await db.scalar(
        select(BillingRate).where(
            BillingRate.id == rate_id,
            BillingRate.organization_id == current_user.organization_id,
        )
    )
    if not rate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing rate not found")

    updates = payload.model_dump(exclude_unset=True)
    if "role_name" in updates or "user_id" in updates:
        role_name, user_id = await validate_billing_rate_payload(
            db,
            organization_id=current_user.organization_id,
            rate_type=rate.rate_type,
            role_name=updates.get("role_name", rate.role_name),
            user_id=updates.get("user_id", rate.user_id),
        )
        rate.role_name = role_name
        rate.user_id = user_id

    for key, value in updates.items():
        if key in {"role_name", "user_id"}:
            continue
        if key == "hourly_rate" and value is not None:
            value = money(value)
        setattr(rate, key, value)
    rate.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(rate)
    return serialize_billing_rate(rate)


@router.delete("/billing-rates/{rate_id}")
async def deactivate_billing_rate(
    rate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    rate = await db.scalar(
        select(BillingRate).where(
            BillingRate.id == rate_id,
            BillingRate.organization_id == current_user.organization_id,
        )
    )
    if not rate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing rate not found")
    rate.is_active = False
    rate.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.get("/billing-rates/effective", response_model=EffectiveBillingRateResponse)
async def get_effective_billing_rate(
    user_id: int = Query(...),
    currency: str = Query(default="USD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    resolved = await get_effective_hourly_rate(db, current_user.organization_id, user_id, normalize_currency(currency))
    return EffectiveBillingRateResponse(
        user_id=user_id,
        currency=normalize_currency(currency),
        hourly_rate=resolved.hourly_rate,
        source=resolved.source,
        rate_id=resolved.rate_id,
    )
