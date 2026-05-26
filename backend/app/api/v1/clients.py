from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, role_guard
from app.db.session import get_db
from app.models.client import Client
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.client import ClientCreate, ClientResponse, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]


def to_response(client: Client) -> ClientResponse:
    return ClientResponse(
        id=client.id,
        organization_id=client.organization_id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        user_id=client.user_id,
        address=client.address,
        notes=client.notes,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


async def validate_client_user(db: AsyncSession, organization_id: int, user_id: int | None) -> User | None:
    if user_id is None:
        return None
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == organization_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Linked user must belong to your organization")
    if user.role != UserRole.client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Linked user must have client role")
    return user


@router.post("", response_model=ClientResponse)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    await validate_client_user(db, current_user.organization_id, payload.user_id)
    now = datetime.now(timezone.utc)
    client = Client(
        organization_id=current_user.organization_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        user_id=payload.user_id,
        address=payload.address,
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return to_response(client)


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    rows = await db.scalars(
        select(Client)
        .where(Client.organization_id == current_user.organization_id)
        .order_by(Client.created_at.desc())
    )
    return [to_response(c) for c in rows.all()]


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await db.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.organization_id == current_user.organization_id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return to_response(client)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await db.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.organization_id == current_user.organization_id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    updates = payload.model_dump(exclude_unset=True)
    if "user_id" in updates:
        await validate_client_user(db, current_user.organization_id, updates["user_id"])
    for key, value in updates.items():
        setattr(client, key, value)
    client.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(client)
    return to_response(client)


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await db.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.organization_id == current_user.organization_id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    await db.delete(client)
    await db.commit()
    return {"ok": True}
