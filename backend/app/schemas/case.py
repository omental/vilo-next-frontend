from datetime import datetime
from pydantic import BaseModel, Field

from app.models.case import CasePriority, CaseStatus


class CaseAssignmentRequest(BaseModel):
    user_ids: list[int]


class AssignedUser(BaseModel):
    id: int
    name: str
    email: str
    role: str
    status: str


class CaseCreate(BaseModel):
    title: str
    description: str | None = None
    client_id: int
    status: CaseStatus = CaseStatus.draft
    priority: CasePriority = CasePriority.medium
    assigned_user_ids: list[int] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    client_id: int | None = None
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    assigned_user_ids: list[int] | None = None


class CaseResponse(BaseModel):
    id: int
    organization_id: int
    title: str
    description: str | None
    client_id: int
    status: str
    priority: str
    created_by: int
    assigned_users: list[AssignedUser]
    created_at: datetime
    updated_at: datetime
    client_name: str | None = None
    case_number: str | None = None


class CaseStatusCount(BaseModel):
    status: str
    count: int


class CaseListResponse(BaseModel):
    items: list[CaseResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int
    total_pages: int
    counts: list[CaseStatusCount] = Field(default_factory=list)
