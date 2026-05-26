from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/expenses", tags=["expenses"])
ALLOWED = ["partner", "admin", "lawyer", "paralegal"]


def ser(e: Expense) -> ExpenseResponse:
    return ExpenseResponse(**{c: getattr(e, c) for c in ExpenseResponse.model_fields.keys()})


async def validate_links(db: AsyncSession, org_id: int, case_id: int | None, client_id: int | None):
    case = None
    if case_id is not None:
        case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == org_id))
        if not case: raise HTTPException(status_code=400, detail="Case must belong to your organization")
    if client_id is not None:
        client = await db.scalar(select(Client).where(Client.id == client_id, Client.organization_id == org_id))
        if not client: raise HTTPException(status_code=400, detail="Client must belong to your organization")
    return case


@router.post("", response_model=ExpenseResponse)
async def create_expense(payload: ExpenseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    case = await validate_links(db, current_user.organization_id, payload.case_id, payload.client_id)
    now = datetime.now(timezone.utc)
    obj = Expense(organization_id=current_user.organization_id, created_by=current_user.id, created_at=now, updated_at=now, billed=False, **payload.model_dump())
    db.add(obj)
    await db.flush()
    if case:
        await create_case_timeline_event(db, organization_id=current_user.organization_id, case_id=case.id, actor_id=current_user.id, event_type="expense_added", title="Expense added", metadata_json={"expense_id": obj.id})
    await db.commit(); await db.refresh(obj)
    return ser(obj)


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(case_id: int | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    q = select(Expense).where(Expense.organization_id == current_user.organization_id)
    if case_id is not None: q = q.where(Expense.case_id == case_id)
    rows = await db.scalars(q.order_by(Expense.expense_date.desc()))
    return [ser(x) for x in rows.all()]


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    obj = await db.scalar(select(Expense).where(Expense.id == expense_id, Expense.organization_id == current_user.organization_id))
    if not obj: raise HTTPException(status_code=404, detail="Expense not found")
    return ser(obj)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: int, payload: ExpenseUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    obj = await db.scalar(select(Expense).where(Expense.id == expense_id, Expense.organization_id == current_user.organization_id))
    if not obj: raise HTTPException(status_code=404, detail="Expense not found")
    updates = payload.model_dump(exclude_unset=True)
    await validate_links(db, current_user.organization_id, updates.get("case_id", obj.case_id), updates.get("client_id", obj.client_id))
    for k, v in updates.items(): setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    await db.commit(); await db.refresh(obj)
    return ser(obj)


@router.delete("/{expense_id}")
async def delete_expense(expense_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    obj = await db.scalar(select(Expense).where(Expense.id == expense_id, Expense.organization_id == current_user.organization_id))
    if not obj: raise HTTPException(status_code=404, detail="Expense not found")
    await db.delete(obj); await db.commit(); return {"ok": True}
