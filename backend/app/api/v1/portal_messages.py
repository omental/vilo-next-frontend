from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.conversation import Conversation, ConversationParticipant, Message
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.conversation import ConversationResponse, MessageCreate, MessageResponse
from app.services.notifications import bulk_create_notifications

router = APIRouter(prefix="/portal/messages", tags=["portal-messages"])


async def get_portal_client(db: AsyncSession, current_user: User) -> Client:
    if current_user.role != UserRole.client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client portal only")
    client = await db.scalar(
        select(Client).where(
            Client.organization_id == current_user.organization_id,
            Client.user_id == current_user.id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client profile not linked")
    return client


async def get_allowed_conversation(db: AsyncSession, client: Client, conversation_id: int) -> Conversation:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == client.organization_id,
            Conversation.conversation_type == "client",
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    part = await db.scalar(
        select(ConversationParticipant).where(
            ConversationParticipant.organization_id == client.organization_id,
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == client.user_id,
        )
    )
    if not part:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.case_id is not None:
        case = await db.scalar(select(Case).where(Case.id == conv.case_id, Case.organization_id == client.organization_id, Case.client_id == client.id))
        if not case:
            raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


async def conversation_summary(db: AsyncSession, conv: Conversation, current_user_id: int) -> ConversationResponse:
    participant_count = len(
        (
            await db.scalars(
                select(ConversationParticipant).where(
                    ConversationParticipant.organization_id == conv.organization_id,
                    ConversationParticipant.conversation_id == conv.id,
                )
            )
        ).all()
    )
    participant = await db.scalar(
        select(ConversationParticipant).where(
            ConversationParticipant.organization_id == conv.organization_id,
            ConversationParticipant.conversation_id == conv.id,
            ConversationParticipant.user_id == current_user_id,
        )
    )
    last_read_at = participant.last_read_at if participant else None
    msg_rows = (
        await db.scalars(
            select(Message)
            .where(Message.organization_id == conv.organization_id, Message.conversation_id == conv.id, Message.deleted_at.is_(None))
            .order_by(Message.created_at.desc())
        )
    ).all()
    latest = msg_rows[0] if msg_rows else None
    unread = 0
    for m in msg_rows:
        if m.sender_id == current_user_id:
            continue
        if last_read_at is None or m.created_at > last_read_at:
            unread += 1
    latest_message = None
    if latest:
        latest_message = MessageResponse(id=latest.id, conversation_id=latest.conversation_id, sender_id=latest.sender_id, parent_message_id=latest.parent_message_id, body=latest.body, created_at=latest.created_at, updated_at=latest.updated_at, deleted_at=latest.deleted_at)
    return ConversationResponse(id=conv.id, organization_id=conv.organization_id, case_id=conv.case_id, conversation_type=conv.conversation_type, title=conv.title, created_by=conv.created_by, created_at=conv.created_at, updated_at=conv.updated_at, participant_count=participant_count, unread_count=unread, latest_message=latest_message)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_portal_conversations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await get_portal_client(db, current_user)
    part_rows = (
        await db.scalars(
            select(ConversationParticipant).where(
                ConversationParticipant.organization_id == client.organization_id,
                ConversationParticipant.user_id == client.user_id,
            )
        )
    ).all()
    convs = []
    for p in part_rows:
        conv = await db.scalar(
            select(Conversation).where(
                Conversation.id == p.conversation_id,
                Conversation.organization_id == client.organization_id,
                Conversation.conversation_type == "client",
            )
        )
        if not conv:
            continue
        if conv.case_id is not None:
            case = await db.scalar(select(Case).where(Case.id == conv.case_id, Case.organization_id == client.organization_id, Case.client_id == client.id))
            if not case:
                continue
        convs.append(conv)
    return [await conversation_summary(db, c, current_user.id) for c in convs]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_portal_conversation(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await get_portal_client(db, current_user)
    conv = await get_allowed_conversation(db, client, conversation_id)
    return await conversation_summary(db, conv, current_user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_portal_messages(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await get_portal_client(db, current_user)
    await get_allowed_conversation(db, client, conversation_id)
    rows = (
        await db.scalars(
            select(Message)
            .where(Message.organization_id == client.organization_id, Message.conversation_id == conversation_id, Message.deleted_at.is_(None))
            .order_by(Message.created_at.asc())
        )
    ).all()
    return [MessageResponse(id=m.id, conversation_id=m.conversation_id, sender_id=m.sender_id, parent_message_id=m.parent_message_id, body=m.body, created_at=m.created_at, updated_at=m.updated_at, deleted_at=m.deleted_at) for m in rows]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def create_portal_message(conversation_id: int, payload: MessageCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await get_portal_client(db, current_user)
    conv = await get_allowed_conversation(db, client, conversation_id)
    if payload.parent_message_id is not None:
        parent = await db.scalar(select(Message).where(Message.id == payload.parent_message_id, Message.organization_id == client.organization_id, Message.conversation_id == conversation_id))
        if not parent:
            raise HTTPException(status_code=400, detail="Parent message not found")
    now = datetime.now(timezone.utc)
    msg = Message(
        organization_id=client.organization_id,
        conversation_id=conversation_id,
        sender_id=current_user.id,
        parent_message_id=payload.parent_message_id,
        body=payload.body,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(msg)
    await db.flush()
    conv.updated_at = now
    participant_ids = (
        await db.scalars(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.organization_id == client.organization_id,
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id != current_user.id,
            )
        )
    ).all()
    await bulk_create_notifications(
        db,
        organization_id=client.organization_id,
        user_ids=list(participant_ids),
        type="message_received",
        title=f"New message in {conv.title or 'conversation'}",
        body=current_user.name,
        metadata_json={"conversation_id": conversation_id, "message_id": msg.id},
    )
    await db.commit()
    await db.refresh(msg)
    return MessageResponse(id=msg.id, conversation_id=msg.conversation_id, sender_id=msg.sender_id, parent_message_id=msg.parent_message_id, body=msg.body, created_at=msg.created_at, updated_at=msg.updated_at, deleted_at=msg.deleted_at)


@router.post("/conversations/{conversation_id}/mark-read")
async def mark_portal_conversation_read(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await get_portal_client(db, current_user)
    await get_allowed_conversation(db, client, conversation_id)
    part = await db.scalar(
        select(ConversationParticipant).where(
            ConversationParticipant.organization_id == client.organization_id,
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == current_user.id,
        )
    )
    part.last_read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}
