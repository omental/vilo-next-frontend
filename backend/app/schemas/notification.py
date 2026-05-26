from datetime import datetime
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    body: str | None
    is_read: bool
    metadata: dict | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int
    unread_count: int


class MarkNotificationsReadRequest(BaseModel):
    notification_ids: list[int] = Field(default_factory=list)
