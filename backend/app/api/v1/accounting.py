from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.operating_account import OperatingAccount
from app.models.user import User
from app.schemas.accounting import (
    AccountingSummaryResponse,
    OperatingAccountCreate,
    OperatingAccountResponse,
)
from app.services.finance import build_accounting_summary, money

router = APIRouter(prefix="/accounting", tags=["accounting"])
MANAGE = ["partner", "admin"]
VIEW = ["partner", "admin", "lawyer"]


def serialize_account(account: OperatingAccount) -> OperatingAccountResponse:
    return OperatingAccountResponse(**{field: getattr(account, field) for field in OperatingAccountResponse.model_fields.keys()})


@router.get("/operating-accounts", response_model=list[OperatingAccountResponse])
async def list_operating_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    rows = await db.scalars(
        select(OperatingAccount)
        .where(OperatingAccount.organization_id == current_user.organization_id)
        .order_by(OperatingAccount.currency.asc(), OperatingAccount.name.asc())
    )
    return [serialize_account(row) for row in rows.all()]


@router.post("/operating-accounts", response_model=OperatingAccountResponse)
async def create_operating_account(
    payload: OperatingAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(MANAGE)),
):
    now = datetime.now(timezone.utc)
    account = OperatingAccount(
        organization_id=current_user.organization_id,
        name=payload.name,
        currency=payload.currency,
        is_default=payload.is_default,
        current_balance=money("0"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return serialize_account(account)


@router.get("/summary", response_model=AccountingSummaryResponse)
async def accounting_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(VIEW)),
):
    return AccountingSummaryResponse(
        organization_id=current_user.organization_id,
        trust_funds_excluded=True,
        currencies=await build_accounting_summary(db, current_user.organization_id),
    )
