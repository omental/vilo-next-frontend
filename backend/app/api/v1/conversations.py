from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.conversation import Conversation, ConversationParticipant, Message
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
    MessageUpdate,
    ParticipantCreate,
    ParticipantResponse,
)
from app.services.notifications import bulk_create_notifications
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/conversations", tags=["conversations"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]
VALID_TYPES = {"internal", "client", "group"}
VALID_PARTICIPANT_ROLES = {"member", "client", "owner"}


async def get_conversation_or_404(db: AsyncSession, org_id: int, conversation_id: int) -> Conversation:
    conv = await db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.organization_id == org_id))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


async def require_participant(db: AsyncSession, org_id: int, conversation_id: int, user_id: int) -> ConversationParticipant:
    part = await db.scalar(
        select(ConversationParticipant).where(
            ConversationParticipant.organization_id == org_id,
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        )
    )
    if not part:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a conversation participant")
    return part


async def conversation_summary(db: AsyncSession, conv: Conversation, current_user_id: int) -> ConversationResponse:
    participant_count = int(
        (await db.scalar(select(func.count(ConversationParticipant.id)).where(ConversationParticipant.conversation_id == conv.id, ConversationParticipant.organization_id == conv.organization_id)))
        or 0
    )
    participant = await db.scalar(
        select(ConversationParticipant).where(
            ConversationParticipant.organization_id == conv.organization_id,
            ConversationParticipant.conversation_id == conv.id,
            ConversationParticipant.user_id == current_user_id,
        )
    )
    last_read_at = participant.last_read_at if participant else None
    unread_filters = [
        Message.organization_id == conv.organization_id,
        Message.conversation_id == conv.id,
        Message.deleted_at.is_(None),
        Message.sender_id != current_user_id,
    ]
    if last_read_at is not None:
        unread_filters.append(Message.created_at > last_read_at)
    unread_count = int((await db.scalar(select(func.count(Message.id)).where(*unread_filters))) or 0)

    latest = await db.scalar(
        select(Message)
        .where(Message.organization_id == conv.organization_id, Message.conversation_id == conv.id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    latest_message = None
    if latest:
        latest_message = MessageResponse(
            id=latest.id,
            conversation_id=latest.conversation_id,
            sender_id=latest.sender_id,
            parent_message_id=latest.parent_message_id,
            body=latest.body,
            created_at=latest.created_at,
            updated_at=latest.updated_at,
            deleted_at=latest.deleted_at,
        )
    return ConversationResponse(
        id=conv.id,
        organization_id=conv.organization_id,
        case_id=conv.case_id,
        conversation_type=conv.conversation_type,
        title=conv.title,
        created_by=conv.created_by,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        participant_count=participant_count,
        unread_count=unread_count,
        latest_message=latest_message,
    )


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    if payload.conversation_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="Invalid conversation type")

    linked_case = None
    if payload.case_id is not None:
        linked_case = await db.scalar(select(Case).where(Case.id == payload.case_id, Case.organization_id == current_user.organization_id))
        if not linked_case:
            raise HTTPException(status_code=400, detail="Case must belong to your organization")

    if payload.conversation_type == "client" and payload.case_id is None:
        raise HTTPException(status_code=400, detail="Client conversations must link to a case")

    participant_ids = set(payload.participant_ids)
    participant_ids.add(current_user.id)

    users = (await db.scalars(select(User).where(User.organization_id == current_user.organization_id, User.id.in_(participant_ids)))).all()
    if len(users) != len(participant_ids):
        raise HTTPException(status_code=400, detail="One or more participants are invalid")

    if payload.conversation_type == "client":
        if not any(u.role == UserRole.client for u in users):
            raise HTTPException(status_code=400, detail="Client conversation requires a client participant")
        client_user_ids = [u.id for u in users if u.role == UserRole.client]
        clients = (await db.scalars(select(Client).where(Client.organization_id == current_user.organization_id, Client.user_id.in_(client_user_ids)))).all()
        if len(clients) != len(client_user_ids):
            raise HTTPException(status_code=400, detail="Client participant must be linked to a client profile")
        if linked_case and any(c.id != linked_case.client_id for c in clients):
            raise HTTPException(status_code=400, detail="Client participant does not match linked case client")

    now = datetime.now(timezone.utc)
    conv = Conversation(
        organization_id=current_user.organization_id,
        case_id=payload.case_id,
        conversation_type=payload.conversation_type,
        title=payload.title,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.flush()

    for uid in participant_ids:
        role = "owner" if uid == current_user.id else "member"
        user = next((u for u in users if u.id == uid), None)
        if user and user.role == UserRole.client:
            role = "client"
        db.add(
            ConversationParticipant(
                organization_id=current_user.organization_id,
                conversation_id=conv.id,
                user_id=uid,
                role=role,
                created_at=now,
            )
        )

    if linked_case:
        event_type = "client_conversation_started" if payload.conversation_type == "client" else "internal_conversation_started"
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=linked_case.id,
            actor_id=current_user.id,
            event_type=event_type,
            title=f"Conversation started: {payload.title or payload.conversation_type}",
            metadata_json={"conversation_id": conv.id, "conversation_type": payload.conversation_type},
        )

    await db.commit()
    return await conversation_summary(db, conv, current_user.id)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    conv_ids = (
        await db.scalars(
            select(ConversationParticipant.conversation_id).where(
                ConversationParticipant.organization_id == current_user.organization_id,
                ConversationParticipant.user_id == current_user.id,
            )
        )
    ).all()
    if not conv_ids:
        return []
    rows = (
        await db.scalars(
            select(Conversation)
            .where(Conversation.organization_id == current_user.organization_id, Conversation.id.in_(conv_ids))
            .order_by(Conversation.updated_at.desc())
        )
    ).all()
    return [await conversation_summary(db, c, current_user.id) for c in rows]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    conv = await get_conversation_or_404(db, current_user.organization_id, conversation_id)
    return await conversation_summary(db, conv, current_user.id)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(conversation_id: int, payload: ConversationUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    conv = await get_conversation_or_404(db, current_user.organization_id, conversation_id)
    if payload.title is not None:
        conv.title = payload.title
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await conversation_summary(db, conv, current_user.id)


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    conv = await get_conversation_or_404(db, current_user.organization_id, conversation_id)
    await db.delete(conv)
    await db.commit()
    return {"ok": True}


@router.post("/{conversation_id}/participants", response_model=ParticipantResponse)
async def add_participant(conversation_id: int, payload: ParticipantCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    if payload.role not in VALID_PARTICIPANT_ROLES:
        raise HTTPException(status_code=400, detail="Invalid participant role")
    conv = await get_conversation_or_404(db, current_user.organization_id, conversation_id)
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    user = await db.scalar(select(User).where(User.id == payload.user_id, User.organization_id == current_user.organization_id))
    if not user:
        raise HTTPException(status_code=400, detail="User must belong to your organization")
    existing = await db.scalar(
        select(ConversationParticipant).where(
            ConversationParticipant.organization_id == current_user.organization_id,
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == payload.user_id,
        )
    )
    if existing:
        return ParticipantResponse(user_id=existing.user_id, role=existing.role, last_read_at=existing.last_read_at, created_at=existing.created_at)
    now = datetime.now(timezone.utc)
    part = ConversationParticipant(
        organization_id=current_user.organization_id,
        conversation_id=conversation_id,
        user_id=payload.user_id,
        role=payload.role,
        created_at=now,
    )
    if conv.conversation_type == "client" and user.role != UserRole.client and payload.role == "client":
        raise HTTPException(status_code=400, detail="Client role participant must be a client user")
    db.add(part)
    conv.updated_at = now
    await db.commit()
    return ParticipantResponse(user_id=part.user_id, role=part.role, last_read_at=part.last_read_at, created_at=part.created_at)


@router.get("/{conversation_id}/participants", response_model=list[ParticipantResponse])
async def list_participants(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    parts = (
        await db.scalars(
            select(ConversationParticipant)
            .where(ConversationParticipant.organization_id == current_user.organization_id, ConversationParticipant.conversation_id == conversation_id)
            .order_by(ConversationParticipant.created_at.asc())
        )
    ).all()
    return [ParticipantResponse(user_id=p.user_id, role=p.role, last_read_at=p.last_read_at, created_at=p.created_at) for p in parts]


@router.delete("/{conversation_id}/participants/{user_id}")
async def remove_participant(conversation_id: int, user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    part = await db.scalar(
        select(ConversationParticipant).where(
            ConversationParticipant.organization_id == current_user.organization_id,
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        )
    )
    if not part:
        raise HTTPException(status_code=404, detail="Participant not found")
    await db.delete(part)
    conv = await get_conversation_or_404(db, current_user.organization_id, conversation_id)
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def create_message(conversation_id: int, payload: MessageCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    if payload.parent_message_id is not None:
        parent = await db.scalar(
            select(Message).where(
                Message.id == payload.parent_message_id,
                Message.organization_id == current_user.organization_id,
                Message.conversation_id == conversation_id,
            )
        )
        if not parent:
            raise HTTPException(status_code=400, detail="Parent message not found")

    now = datetime.now(timezone.utc)
    msg = Message(
        organization_id=current_user.organization_id,
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
    conv = await get_conversation_or_404(db, current_user.organization_id, conversation_id)
    conv.updated_at = now
    participant_ids = (
        await db.scalars(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.organization_id == current_user.organization_id,
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id != current_user.id,
            )
        )
    ).all()
    await bulk_create_notifications(
        db,
        organization_id=current_user.organization_id,
        user_ids=list(participant_ids),
        type="message_received",
        title=f"New message in {conv.title or 'conversation'}",
        body=current_user.name,
        metadata_json={"conversation_id": conversation_id, "message_id": msg.id},
    )
    await db.commit()
    await db.refresh(msg)
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        parent_message_id=msg.parent_message_id,
        body=msg.body,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
        deleted_at=msg.deleted_at,
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    rows = (
        await db.scalars(
            select(Message)
            .where(
                Message.organization_id == current_user.organization_id,
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.asc())
        )
    ).all()
    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            sender_id=m.sender_id,
            parent_message_id=m.parent_message_id,
            body=m.body,
            created_at=m.created_at,
            updated_at=m.updated_at,
            deleted_at=m.deleted_at,
        )
        for m in rows
    ]


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def update_message(message_id: int, payload: MessageUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    msg = await db.scalar(select(Message).where(Message.id == message_id, Message.organization_id == current_user.organization_id, Message.deleted_at.is_(None)))
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    await require_participant(db, current_user.organization_id, msg.conversation_id, current_user.id)
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only sender can edit message")
    msg.body = payload.body
    msg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return MessageResponse(id=msg.id, conversation_id=msg.conversation_id, sender_id=msg.sender_id, parent_message_id=msg.parent_message_id, body=msg.body, created_at=msg.created_at, updated_at=msg.updated_at, deleted_at=msg.deleted_at)


@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    msg = await db.scalar(select(Message).where(Message.id == message_id, Message.organization_id == current_user.organization_id, Message.deleted_at.is_(None)))
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    await require_participant(db, current_user.organization_id, msg.conversation_id, current_user.id)
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only sender can delete message")
    msg.deleted_at = datetime.now(timezone.utc)
    msg.updated_at = msg.deleted_at
    await db.commit()
    return {"ok": True}


@router.post("/{conversation_id}/mark-read")
async def mark_conversation_read(conversation_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_STAFF))):
    part = await require_participant(db, current_user.organization_id, conversation_id, current_user.id)
    part.last_read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}
