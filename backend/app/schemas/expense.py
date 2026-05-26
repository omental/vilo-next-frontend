from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class ExpenseCreate(BaseModel):
    case_id: int | None = None
    client_id: int | None = None
    description: str
    category: str | None = None
    amount: Decimal
    expense_date: date
    billable: bool = True


class ExpenseUpdate(BaseModel):
    case_id: int | None = None
    client_id: int | None = None
    description: str | None = None
    category: str | None = None
    amount: Decimal | None = None
    expense_date: date | None = None
    billable: bool | None = None
    billed: bool | None = None


class ExpenseResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int | None
    client_id: int | None
    created_by: int
    description: str
    category: str | None
    amount: Decimal
    expense_date: date
    billable: bool
    billed: bool
    created_at: datetime
    updated_at: datetime
