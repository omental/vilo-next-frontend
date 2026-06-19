from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int | None
    client_id: int | None
    uploaded_by: int
    title: str
    description: str | None
    file_name: str
    file_type: str | None
    file_size: int | None
    category: str | None
    visibility: str
    version: int
    version_source: str | None = None
    version_note: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    visibility: str | None = None


class DocumentVersionResponse(BaseModel):
    id: int
    document_id: int
    organization_id: int
    file_name: str
    file_type: str | None
    file_size: int | None
    version_number: int
    uploaded_by: int
    source: str | None = None
    notes: str | None
    version_note: str | None = None
    created_at: datetime


class DocumentEditableContentResponse(BaseModel):
    document_id: int
    file_type: str | None
    editable: bool
    mode: str | None = None
    content: str = ""
    warning: str | None = None
    reason: str | None = None


class DocumentEditableContentUpdate(BaseModel):
    content: str
    version_note: str | None = None
