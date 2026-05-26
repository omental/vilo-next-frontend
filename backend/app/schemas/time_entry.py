from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class TimeEntryCreate(BaseModel):
    case_id: int
    user_id: int
    description: str
    hours: Decimal
    rate: Decimal
    billable: bool = True
    entry_date: date


class TimeEntryUpdate(BaseModel):
    case_id: int | None = None
    user_id: int | None = None
    description: str | None = None
    hours: Decimal | None = None
    rate: Decimal | None = None
    billable: bool | None = None
    billed: bool | None = None
    entry_date: date | None = None


class TimeEntryResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int
    user_id: int
    description: str
    hours: Decimal
    rate: Decimal
    billable: bool
    billed: bool
    entry_date: date
    created_at: datetime
    updated_at: datetime
