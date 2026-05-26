from datetime import datetime
from pydantic import BaseModel


class TaskCreate(BaseModel):
    case_id: int | None = None
    assigned_to: int | None = None
    title: str
    description: str | None = None
    status: str = "pending"
    priority: str = "medium"
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    case_id: int | None = None
    assigned_to: int | None = None
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    completed_at: datetime | None = None


class TaskResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int | None
    assigned_to: int | None
    created_by: int
    title: str
    description: str | None
    status: str
    priority: str
    due_date: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
