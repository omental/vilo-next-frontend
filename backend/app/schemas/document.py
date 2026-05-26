from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int | None
    uploaded_by: int
    title: str
    description: str | None
    file_name: str
    file_path: str
    file_type: str | None
    file_size: int | None
    category: str | None
    visibility: str
    version: int
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    visibility: str | None = None
