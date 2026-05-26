from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_organization, get_current_user
from app.db.session import get_db
from app.models.case import Case
from app.models.case_note import CaseNote
from app.models.case_timeline_event import CaseTimelineEvent
from app.models.client import Client
from app.models.client_intake import ClientIntake
from app.models.document import Document
from app.models.enums import UserRole
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.invoice import InvoiceLineItemResponse
from app.schemas.portal import (
    ClientIntakeCreate,
    ClientIntakeResponse,
    ClientIntakeUpdate,
    PortalCaseNoteResponse,
    PortalCaseResponse,
    PortalDocumentResponse,
    PortalInvoiceDetailResponse,
    PortalInvoiceResponse,
    PortalProfileResponse,
    PortalTimelineResponse,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/portal", tags=["portal"])
SAFE_TIMELINE_EVENTS = {
    "case_created",
    "case_updated",
    "document_uploaded",
    "note_added",
    "invoice_sent",
    "invoice_paid",
    "trust_applied_to_invoice",
}


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


def normalize_pagination(page: int, page_size: int) -> tuple[int, int, int]:
    page = max(page, 1)
    page_size = max(1, min(page_size, 50))
    return page, page_size, (page - 1) * page_size


def case_to_response(case: Case) -> PortalCaseResponse:
    return PortalCaseResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        status=case.status.value if hasattr(case.status, "value") else str(case.status),
        priority=case.priority.value if hasattr(case.priority, "value") else str(case.priority),
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def invoice_to_response(invoice: Invoice) -> PortalInvoiceResponse:
    return PortalInvoiceResponse(
        id=invoice.id,
        case_id=invoice.case_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total=invoice.total,
        paid_amount=invoice.paid_amount,
        balance_due=invoice.balance_due,
        notes=invoice.notes,
        created_at=invoice.created_at,
    )


def intake_to_response(intake: ClientIntake) -> ClientIntakeResponse:
    return ClientIntakeResponse(
        id=intake.id,
        organization_id=intake.organization_id,
        client_id=intake.client_id,
        submitted_by=intake.submitted_by,
        status=intake.status,
        full_name=intake.full_name,
        email=intake.email,
        phone=intake.phone,
        address=intake.address,
        matter_type=intake.matter_type,
        description=intake.description,
        submitted_at=intake.submitted_at,
        created_at=intake.created_at,
        updated_at=intake.updated_at,
    )


async def get_client_case_or_404(db: AsyncSession, organization_id: int, client_id: int, case_id: int) -> Case:
    case = await db.scalar(
        select(Case).where(
            Case.id == case_id,
            Case.organization_id == organization_id,
            Case.client_id == client_id,
        )
    )
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


@router.get("/me", response_model=PortalProfileResponse)
async def portal_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_organization=Depends(get_current_organization),
):
    client = await get_portal_client(db, current_user)
    return PortalProfileResponse(
        client_id=client.id,
        organization_id=client.organization_id,
        organization_name=current_organization.name,
        name=client.name,
        email=client.email,
        phone=client.phone,
        address=client.address,
        notes=client.notes,
        linked_user={
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": current_user.role.value,
        },
    )


@router.get("/cases")
async def portal_cases(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    page, page_size, offset = normalize_pagination(page, page_size)
    total = int(
        (await db.scalar(select(func.count(Case.id)).where(Case.organization_id == client.organization_id, Case.client_id == client.id)))
        or 0
    )
    rows = await db.scalars(
        select(Case)
        .where(Case.organization_id == client.organization_id, Case.client_id == client.id)
        .order_by(Case.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return {"items": [case_to_response(case) for case in rows.all()], "total": total, "page": page, "page_size": page_size}


@router.get("/cases/{case_id}", response_model=PortalCaseResponse)
async def portal_case_detail(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    case = await get_client_case_or_404(db, client.organization_id, client.id, case_id)
    return case_to_response(case)


@router.get("/cases/{case_id}/timeline", response_model=list[PortalTimelineResponse])
async def portal_case_timeline(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    await get_client_case_or_404(db, client.organization_id, client.id, case_id)

    rows = await db.scalars(
        select(CaseTimelineEvent)
        .where(
            CaseTimelineEvent.organization_id == client.organization_id,
            CaseTimelineEvent.case_id == case_id,
            CaseTimelineEvent.event_type.in_(SAFE_TIMELINE_EVENTS),
        )
        .order_by(CaseTimelineEvent.created_at.desc())
    )

    output: list[PortalTimelineResponse] = []
    for event in rows.all():
        if event.event_type == "document_uploaded":
            doc_id = (event.metadata_json or {}).get("document_id")
            if not doc_id:
                continue
            doc = await db.scalar(
                select(Document).where(
                    Document.id == doc_id,
                    Document.organization_id == client.organization_id,
                    Document.case_id == case_id,
                    Document.visibility == "client_visible",
                )
            )
            if not doc:
                continue
        if event.event_type == "note_added":
            note_id = (event.metadata_json or {}).get("note_id")
            if not note_id:
                continue
            note = await db.scalar(
                select(CaseNote).where(
                    CaseNote.id == note_id,
                    CaseNote.organization_id == client.organization_id,
                    CaseNote.case_id == case_id,
                    CaseNote.visibility == "client_visible",
                )
            )
            if not note:
                continue
        output.append(
            PortalTimelineResponse(
                id=event.id,
                event_type=event.event_type,
                title=event.title,
                description=None,
                created_at=event.created_at,
            )
        )
    return output


@router.get("/documents")
async def portal_documents(
    case_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    page, page_size, offset = normalize_pagination(page, page_size)
    base_query = (
        select(Document.id)
        .join(Case, Document.case_id == Case.id)
        .where(
            Document.organization_id == client.organization_id,
            Document.visibility == "client_visible",
            Case.client_id == client.id,
        )
    )
    if case_id is not None:
        base_query = base_query.where(Document.case_id == case_id)

    total = int((await db.scalar(select(func.count()).select_from(base_query.subquery()))) or 0)
    rows = await db.scalars(
        select(Document)
        .where(Document.id.in_(base_query))
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return {
        "items": [
            PortalDocumentResponse(
                id=doc.id,
                case_id=doc.case_id,
                title=doc.title,
                description=doc.description,
                file_name=doc.file_name,
                file_type=doc.file_type,
                category=doc.category,
                created_at=doc.created_at,
            )
            for doc in rows.all()
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/documents/{document_id}/download")
async def portal_document_download(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    row = await db.execute(
        select(Document)
        .join(Case, Document.case_id == Case.id)
        .where(
            Document.id == document_id,
            Document.organization_id == client.organization_id,
            Document.visibility == "client_visible",
            Case.client_id == client.id,
        )
    )
    doc = row.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return FileResponse(path=str(path), filename=doc.file_name, media_type=doc.file_type or "application/octet-stream")


@router.get("/notes")
async def portal_notes(
    case_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    page, page_size, offset = normalize_pagination(page, page_size)
    base_query = (
        select(CaseNote.id)
        .join(Case, CaseNote.case_id == Case.id)
        .where(
            CaseNote.organization_id == client.organization_id,
            CaseNote.visibility == "client_visible",
            Case.client_id == client.id,
        )
    )
    if case_id is not None:
        base_query = base_query.where(CaseNote.case_id == case_id)

    total = int((await db.scalar(select(func.count()).select_from(base_query.subquery()))) or 0)
    rows = await db.scalars(
        select(CaseNote)
        .where(CaseNote.id.in_(base_query))
        .order_by(CaseNote.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return {
        "items": [
            PortalCaseNoteResponse(
                id=note.id,
                case_id=note.case_id,
                note=note.note,
                visibility=note.visibility,
                created_at=note.created_at,
                updated_at=note.updated_at,
            )
            for note in rows.all()
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/invoices")
async def portal_invoices(
    case_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    page, page_size, offset = normalize_pagination(page, page_size)
    conditions = [Invoice.organization_id == client.organization_id, Invoice.client_id == client.id]
    if case_id is not None:
        conditions.append(Invoice.case_id == case_id)

    total = int((await db.scalar(select(func.count(Invoice.id)).where(*conditions))) or 0)
    rows = await db.scalars(
        select(Invoice).where(*conditions).order_by(Invoice.created_at.desc()).offset(offset).limit(page_size)
    )
    return {"items": [invoice_to_response(inv) for inv in rows.all()], "total": total, "page": page, "page_size": page_size}


@router.get("/invoices/{invoice_id}", response_model=PortalInvoiceDetailResponse)
async def portal_invoice_detail(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    invoice = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.organization_id == client.organization_id, Invoice.client_id == client.id)
        .options(selectinload(Invoice.line_items))
    )
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    base = invoice_to_response(invoice).model_dump()
    return PortalInvoiceDetailResponse(
        **base,
        line_items=[InvoiceLineItemResponse(**{f: getattr(li, f) for f in InvoiceLineItemResponse.model_fields.keys()}) for li in invoice.line_items],
    )


@router.post("/intake", response_model=ClientIntakeResponse)
async def create_intake(
    payload: ClientIntakeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    now = datetime.now(timezone.utc)
    intake = ClientIntake(
        organization_id=client.organization_id,
        client_id=client.id,
        submitted_by=current_user.id,
        status="draft",
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
        matter_type=payload.matter_type,
        description=payload.description,
        submitted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(intake)
    await db.commit()
    await db.refresh(intake)
    return intake_to_response(intake)


@router.get("/intake", response_model=list[ClientIntakeResponse])
async def list_intakes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    rows = await db.scalars(
        select(ClientIntake)
        .where(ClientIntake.organization_id == client.organization_id, ClientIntake.client_id == client.id)
        .order_by(ClientIntake.created_at.desc())
    )
    return [intake_to_response(i) for i in rows.all()]


@router.patch("/intake/{intake_id}", response_model=ClientIntakeResponse)
async def update_intake(
    intake_id: int,
    payload: ClientIntakeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    intake = await db.scalar(
        select(ClientIntake).where(
            ClientIntake.id == intake_id,
            ClientIntake.organization_id == client.organization_id,
            ClientIntake.client_id == client.id,
        )
    )
    if not intake:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intake not found")
    if intake.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Submitted intake is read-only")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(intake, key, value)
    intake.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(intake)
    return intake_to_response(intake)


@router.post("/intake/{intake_id}/submit", response_model=ClientIntakeResponse)
async def submit_intake(
    intake_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await get_portal_client(db, current_user)
    intake = await db.scalar(
        select(ClientIntake).where(
            ClientIntake.id == intake_id,
            ClientIntake.organization_id == client.organization_id,
            ClientIntake.client_id == client.id,
        )
    )
    if not intake:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intake not found")
    if intake.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Intake already submitted")
    now = datetime.now(timezone.utc)
    intake.status = "submitted"
    intake.submitted_at = now
    intake.updated_at = now
    await log_audit_event(
        db,
        organization_id=client.organization_id,
        user_id=current_user.id,
        action="portal_intake_submitted",
        entity_type="client_intake",
        entity_id=str(intake.id),
        description="Client intake submitted from portal",
        metadata_json={"client_id": client.id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(intake)
    return intake_to_response(intake)
