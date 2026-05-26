from datetime import datetime
from pydantic import BaseModel


class CaseNoteCreate(BaseModel):
    note: str
    visibility: str = "internal"


class CaseNoteUpdate(BaseModel):
    note: str | None = None
    visibility: str | None = None


class CaseNoteResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int
    created_by: int
    note: str
    visibility: str
    created_at: datetime
    updated_at: datetime
