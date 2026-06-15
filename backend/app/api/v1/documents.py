import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUpdate, DocumentVersionResponse
from app.services.audit import log_audit_event
from app.services.email import build_document_shared_email
from app.services.jobs import enqueue_email
from app.services.notifications import create_notification
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png", "txt"}
VALID_VISIBILITY = {"internal", "client_visible"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
STORAGE_ROOT = Path("backend/storage/documents")


def to_response(document: Document) -> DocumentResponse:
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


def to_version_response(version: DocumentVersion) -> DocumentVersionResponse:
    return DocumentVersionResponse(
        id=version.id,
        document_id=version.document_id,
        organization_id=version.organization_id,
        file_name=version.file_name,
        file_type=version.file_type,
        file_size=version.file_size,
        version_number=version.version_number,
        uploaded_by=version.uploaded_by,
        notes=version.notes,
        created_at=version.created_at,
    )


async def validate_case(db: AsyncSession, organization_id: int, case_id: int | None):
    if case_id is None:
        return None
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == organization_id))
    if not case:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case must belong to your organization")
    return case


async def validate_client(db: AsyncSession, organization_id: int, client_id: int | None):
    if client_id is None:
        return None
    client = await db.scalar(select(Client).where(Client.id == client_id, Client.organization_id == organization_id))
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client must belong to your organization")
    return client


def safe_original_name(original: str) -> str:
    name = os.path.basename((original or "").strip())
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    return name


def validate_extension(file_name: str) -> str:
    parts = file_name.rsplit(".", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension is required")
    ext = parts[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    return ext


def persist_file(organization_id: int, original_name: str, data: bytes) -> tuple[str, str]:
    ext = validate_extension(original_name)
    org_dir = STORAGE_ROOT / str(organization_id)
    org_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.{ext}"
    file_path = org_dir / stored_name
    file_path.write_bytes(data)
    return str(file_path), stored_name


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    title: str = Form(...),
    description: str | None = Form(default=None),
    category: str | None = Form(default=None),
    visibility: str = Form(default="internal"),
    case_id: int | None = Form(default=None),
    client_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    request: Request = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    if visibility not in VALID_VISIBILITY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visibility")
    case = await validate_case(db, current_user.organization_id, case_id)
    client = await validate_client(db, current_user.organization_id, client_id)
    if case is not None and client is not None and case.client_id != client.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case does not belong to client")
    resolved_client_id = client.id if client is not None else (case.client_id if case is not None else None)

    original_name = safe_original_name(file.filename or "")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds upload size limit")

    file_path, _stored_name = persist_file(current_user.organization_id, original_name, data)

    now = datetime.now(timezone.utc)
    document = Document(
        organization_id=current_user.organization_id,
        case_id=case_id,
        client_id=resolved_client_id,
        uploaded_by=current_user.id,
        title=title,
        description=description,
        file_name=original_name,
        file_path=str(file_path),
        file_type=file.content_type,
        file_size=len(data),
        category=category,
        visibility=visibility,
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
        action="document_uploaded",
        entity_type="document",
        entity_id=str(document.id),
        description=f"Document uploaded: {document.title}",
        metadata_json={"case_id": document.case_id, "visibility": document.visibility},
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    if case is not None:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=case.id,
            actor_id=current_user.id,
            event_type="document_uploaded",
            title=f"Document uploaded: {title}",
            metadata_json={"document_id": document.id, "file_name": original_name},
        )
    if visibility == "client_visible" and case is not None:
        client = await db.scalar(select(Client).where(Client.id == case.client_id, Client.organization_id == current_user.organization_id))
        if client and client.user_id:
            await create_notification(
                db,
                organization_id=current_user.organization_id,
                user_id=client.user_id,
                type="document_shared",
                title=f"New shared document: {title}",
                body="A document has been shared with you in the client portal.",
                metadata_json={"document_id": document.id, "case_id": case.id},
            )
            if background_tasks and client.email:
                subject, html_body, text_body = build_document_shared_email(
                    client_name=client.name or "Client",
                    document_title=document.title,
                    document_id=document.id,
                )
                enqueue_email(background_tasks, to_email=client.email, subject=subject, html_body=html_body, text_body=text_body)

    await db.commit()
    await db.refresh(document)
    return to_response(document)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    case_id: int | None = None,
    client_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    query = select(Document).where(Document.organization_id == current_user.organization_id)
    if case_id is not None:
        query = query.where(Document.case_id == case_id)
    if client_id is not None:
        query = query.where(Document.client_id == client_id)
    rows = await db.scalars(query.order_by(Document.created_at.desc()))
    return [to_response(d) for d in rows.all()]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == current_user.organization_id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return to_response(doc)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == current_user.organization_id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return FileResponse(path=str(path), filename=doc.file_name, media_type=doc.file_type or "application/octet-stream")


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    payload: DocumentUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == current_user.organization_id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    updates = payload.model_dump(exclude_unset=True)
    if "visibility" in updates and updates["visibility"] not in VALID_VISIBILITY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visibility")
    for key, value in updates.items():
        setattr(doc, key, value)
    doc.updated_at = datetime.now(timezone.utc)

    if doc.case_id:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=doc.case_id,
            actor_id=current_user.id,
            event_type="document_updated",
            title=f"Document updated: {doc.title}",
            metadata_json={"document_id": doc.id},
        )
    if updates.get("visibility") == "client_visible" and doc.case_id is not None:
        case = await db.scalar(select(Case).where(Case.id == doc.case_id, Case.organization_id == current_user.organization_id))
        if case:
            client = await db.scalar(select(Client).where(Client.id == case.client_id, Client.organization_id == current_user.organization_id))
            if client and client.user_id:
                await create_notification(
                    db,
                    organization_id=current_user.organization_id,
                    user_id=client.user_id,
                    type="document_shared",
                    title=f"Document shared: {doc.title}",
                    body="A document has been shared with you in the client portal.",
                    metadata_json={"document_id": doc.id, "case_id": case.id},
                )
                if client.email:
                    subject, html_body, text_body = build_document_shared_email(
                        client_name=client.name or "Client",
                        document_title=doc.title,
                        document_id=doc.id,
                    )
                    enqueue_email(background_tasks, to_email=client.email, subject=subject, html_body=html_body, text_body=text_body)

    await db.commit()
    await db.refresh(doc)
    return to_response(doc)


@router.post("/{document_id}/replace", response_model=DocumentResponse)
async def replace_document(
    document_id: int,
    file: UploadFile = File(...),
    notes: str | None = Form(default=None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == current_user.organization_id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    previous_path = doc.file_path
    previous_name = doc.file_name
    previous_type = doc.file_type
    previous_size = doc.file_size
    previous_version = doc.version

    original_name = safe_original_name(file.filename or "")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds upload size limit")

    file_path, _stored_name = persist_file(current_user.organization_id, original_name, data)
    now = datetime.now(timezone.utc)

    version_row = DocumentVersion(
        document_id=doc.id,
        organization_id=doc.organization_id,
        file_name=previous_name,
        file_path=previous_path,
        file_type=previous_type,
        file_size=previous_size,
        version_number=previous_version,
        uploaded_by=current_user.id,
        notes=notes,
        created_at=now,
    )
    db.add(version_row)

    doc.file_name = original_name
    doc.file_path = file_path
    doc.file_type = file.content_type
    doc.file_size = len(data)
    doc.version = previous_version + 1
    doc.uploaded_by = current_user.id
    doc.updated_at = now

    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="document_replaced",
        entity_type="document",
        entity_id=str(doc.id),
        description=f"Document replaced: {doc.title}",
        metadata_json={"previous_version": previous_version, "new_version": doc.version},
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    if doc.case_id:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=doc.case_id,
            actor_id=current_user.id,
            event_type="document_replaced",
            title=f"Document replaced: {doc.title}",
            metadata_json={"document_id": doc.id, "version": doc.version},
        )

    await db.commit()
    await db.refresh(doc)
    return to_response(doc)


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == current_user.organization_id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    rows = await db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id, DocumentVersion.organization_id == current_user.organization_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    return [to_version_response(row) for row in rows.all()]


@router.get("/{document_id}/versions/{version_id}/download")
async def download_document_version(
    document_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == current_user.organization_id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    version = await db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
            DocumentVersion.organization_id == current_user.organization_id,
        )
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    path = Path(version.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return FileResponse(path=str(path), filename=version.file_name, media_type=version.file_type or "application/octet-stream")


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == current_user.organization_id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.case_id:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=doc.case_id,
            actor_id=current_user.id,
            event_type="document_deleted",
            title=f"Document deleted: {doc.title}",
            metadata_json={"document_id": doc.id, "file_name": doc.file_name},
        )
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="document_deleted",
        entity_type="document",
        entity_id=str(doc.id),
        description=f"Document deleted: {doc.title}",
        metadata_json={"case_id": doc.case_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    path = Path(doc.file_path)
    if path.exists():
        path.unlink(missing_ok=True)

    await db.delete(doc)
    await db.commit()
    return {"ok": True}
