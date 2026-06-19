from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.client import Client, ClientAssignment
from app.models.document import Document
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.schemas.client import AssignedUser, ClientCreate, ClientResponse, ClientUpdate
from app.services.audit import log_audit_event

router = APIRouter(prefix="/clients", tags=["clients"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
STORAGE_ROOT = Path("backend/storage/documents")


def to_response(client: Client) -> ClientResponse:
    assigned_users = [
        AssignedUser(
            id=assignment.user.id,
            name=assignment.user.name,
            email=assignment.user.email,
            role=assignment.user.role.value,
            status=assignment.user.status.value,
        )
        for assignment in getattr(client, "assignments", [])
        if getattr(assignment, "user", None) is not None
    ]
    return ClientResponse(
        id=client.id,
        organization_id=client.organization_id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        user_id=client.user_id,
        address=client.address,
        notes=client.notes,
        client_type=client.client_type,
        trn_no=client.trn_no,
        occupation=client.occupation,
        preferred_contact_method=client.preferred_contact_method,
        date_of_birth=client.date_of_birth,
        billing_currency=client.billing_currency,
        archived_at=client.archived_at,
        assigned_users=assigned_users,
        assigned_user_ids=[user.id for user in assigned_users],
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


def normalize_client_type(value: str | None) -> str:
    if not value:
        return "individual"
    normalized = value.strip().lower()
    if normalized not in {"individual", "corporate"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_type must be 'individual' or 'corporate'")
    return normalized


async def get_client_for_org(db: AsyncSession, organization_id: int, client_id: int) -> Client:
    client = await db.scalar(
        select(Client)
        .where(
            Client.id == client_id,
            Client.organization_id == organization_id,
        )
        .options(selectinload(Client.assignments).selectinload(ClientAssignment.user))
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


def to_document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        organization_id=document.organization_id,
        case_id=document.case_id,
        client_id=document.client_id,
        uploaded_by=document.uploaded_by,
        title=document.title,
        description=document.description,
        file_name=document.file_name,
        file_type=document.file_type,
        file_size=document.file_size,
        category=document.category,
        visibility=document.visibility,
        version=document.version,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _safe_original_name(original: str) -> str:
    name = Path(original or "").name.strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    return name


def _validate_extension(file_name: str) -> str:
    parts = file_name.rsplit(".", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension is required")
    ext = parts[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    return ext


async def validate_client_user(db: AsyncSession, organization_id: int, user_id: int | None) -> User | None:
    if user_id is None:
        return None
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == organization_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Linked user must belong to your organization")
    if user.role != UserRole.client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Linked user must have client role")
    return user


async def validate_assignments(db: AsyncSession, organization_id: int, user_ids: list[int]) -> list[User]:
    if not user_ids:
        return []
    rows = await db.scalars(select(User).where(User.organization_id == organization_id, User.id.in_(user_ids)))
    users = rows.all()
    if len(users) != len(set(user_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more assigned users are invalid")
    if any(user.role == UserRole.client for user in users):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned users must be staff members")
    return users


async def sync_client_assignments(client: Client, users: list[User], db: AsyncSession) -> None:
    wanted = {user.id for user in users}
    existing_by_user = {assignment.user_id: assignment for assignment in getattr(client, "assignments", [])}

    kept_assignments = []
    for assignment in list(getattr(client, "assignments", [])):
        if assignment.user_id in wanted:
            kept_assignments.append(assignment)
            continue
        await db.delete(assignment)

    client.assignments = kept_assignments
    for user in users:
        if user.id in existing_by_user:
            continue
        assignment = ClientAssignment(client_id=client.id, user_id=user.id)
        if hasattr(user, "_sa_instance_state"):
            assignment.user = user
        else:
            assignment.__dict__["user"] = user
        client.assignments.append(assignment)
        db.add(assignment)


@router.post("", response_model=ClientResponse)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    await validate_client_user(db, current_user.organization_id, payload.user_id)
    assigned_users = await validate_assignments(db, current_user.organization_id, payload.assigned_user_ids)
    now = datetime.now(timezone.utc)
    client = Client(
        organization_id=current_user.organization_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        user_id=payload.user_id,
        address=payload.address,
        notes=payload.notes,
        client_type=normalize_client_type(payload.client_type),
        trn_no=payload.trn_no,
        occupation=payload.occupation,
        preferred_contact_method=payload.preferred_contact_method,
        date_of_birth=payload.date_of_birth,
        billing_currency=payload.billing_currency or "JMD",
        archived_at=payload.archived_at,
        created_at=now,
        updated_at=now,
    )
    db.add(client)
    await db.flush()
    await sync_client_assignments(client, assigned_users, db)
    await db.commit()
    client = await get_client_for_org(db, current_user.organization_id, client.id)
    return to_response(client)


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    status_filter: str = Query("all", alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    query = (
        select(Client)
        .where(Client.organization_id == current_user.organization_id)
        .options(selectinload(Client.assignments).selectinload(ClientAssignment.user))
    )
    if status_filter == "active":
        query = query.where(Client.archived_at.is_(None))
    elif status_filter == "archived":
        query = query.where(Client.archived_at.is_not(None))
    elif status_filter != "all":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be one of: all, active, archived")

    rows = await db.scalars(query.order_by(Client.created_at.desc()))
    return [to_response(c) for c in rows.all()]


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await get_client_for_org(db, current_user.organization_id, client_id)
    return to_response(client)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await get_client_for_org(db, current_user.organization_id, client_id)

    updates = payload.model_dump(exclude_unset=True, exclude={"assigned_user_ids"})
    if "user_id" in updates:
        await validate_client_user(db, current_user.organization_id, updates["user_id"])
    if "client_type" in updates and updates["client_type"] is not None:
        updates["client_type"] = normalize_client_type(updates["client_type"])
    for key, value in updates.items():
        setattr(client, key, value)
    if payload.assigned_user_ids is not None:
        users = await validate_assignments(db, current_user.organization_id, payload.assigned_user_ids)
        await sync_client_assignments(client, users, db)
    client.updated_at = datetime.now(timezone.utc)

    await db.commit()
    client = await get_client_for_org(db, current_user.organization_id, client.id)
    return to_response(client)


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await get_client_for_org(db, current_user.organization_id, client_id)

    await db.delete(client)
    await db.commit()
    return {"ok": True}


@router.post("/{client_id}/id-documents", response_model=DocumentResponse)
async def upload_client_id_document(
    client_id: int,
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await get_client_for_org(db, current_user.organization_id, client_id)

    original_name = _safe_original_name(file.filename or "")
    ext = _validate_extension(original_name)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds upload size limit")

    org_dir = STORAGE_ROOT / str(current_user.organization_id) / "client_ids" / str(client.id)
    org_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.{ext}"
    file_path = org_dir / stored_name
    file_path.write_bytes(data)

    now = datetime.now(timezone.utc)
    document = Document(
        organization_id=current_user.organization_id,
        client_id=client.id,
        case_id=None,
        uploaded_by=current_user.id,
        title=f"ID Document - {original_name}",
        description="Client identity document",
        file_name=original_name,
        file_path=str(file_path),
        file_type=file.content_type,
        file_size=len(data),
        category="client_id",
        visibility="internal",
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    await db.flush()
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="client_id_document_uploaded",
        entity_type="document",
        entity_id=str(document.id),
        description=f"Client ID document uploaded: {document.file_name}",
        metadata_json={"client_id": client.id},
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    await db.commit()
    await db.refresh(document)
    return to_document_response(document)


@router.get("/{client_id}/id-documents", response_model=list[DocumentResponse])
async def list_client_id_documents(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    client = await get_client_for_org(db, current_user.organization_id, client_id)
    rows = await db.scalars(
        select(Document)
        .where(
            Document.organization_id == current_user.organization_id,
            Document.client_id == client.id,
            Document.category == "client_id",
        )
        .order_by(Document.created_at.desc())
    )
    return [to_document_response(d) for d in rows.all()]


async def get_client_document_for_org(
    db: AsyncSession,
    organization_id: int,
    client_id: int,
    document_id: int,
) -> Document:
    await get_client_for_org(db, organization_id, client_id)
    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
            Document.client_id == client_id,
            Document.category == "client_id",
        )
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.get("/{client_id}/id-documents/{document_id}/download")
async def download_client_id_document(
    client_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await get_client_document_for_org(db, current_user.organization_id, client_id, document_id)
    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return FileResponse(path=str(path), filename=doc.file_name, media_type=doc.file_type or "application/octet-stream")


@router.delete("/{client_id}/id-documents/{document_id}")
async def delete_client_id_document(
    client_id: int,
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await get_client_document_for_org(db, current_user.organization_id, client_id, document_id)
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="client_id_document_deleted",
        entity_type="document",
        entity_id=str(doc.id),
        description=f"Client ID document deleted: {doc.file_name}",
        metadata_json={"client_id": client_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    path = Path(doc.file_path)
    if path.exists():
        path.unlink(missing_ok=True)
    await db.delete(doc)
    await db.commit()
    return {"ok": True}
