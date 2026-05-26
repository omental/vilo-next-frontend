from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    description: str | None
    metadata: dict | None = None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
