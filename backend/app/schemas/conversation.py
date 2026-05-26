from datetime import datetime
from pydantic import BaseModel, Field


class ParticipantCreate(BaseModel):
    user_id: int
    role: str = "member"


class ParticipantResponse(BaseModel):
    user_id: int
    role: str
    last_read_at: datetime | None
    created_at: datetime


class MessageCreate(BaseModel):
    body: str
    parent_message_id: int | None = None


class MessageUpdate(BaseModel):
    body: str


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    parent_message_id: int | None
    body: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ConversationCreate(BaseModel):
    case_id: int | None = None
    conversation_type: str
    title: str | None = None
    participant_ids: list[int] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int | None
    conversation_type: str
    title: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime
    participant_count: int
    unread_count: int
    latest_message: MessageResponse | None = None
