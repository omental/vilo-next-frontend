from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.enums import UserRole
from app.models.expense import Expense
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.organization import Organization
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.invoice import (
    InvoiceClientSummary,
    InvoiceCreate,
    InvoiceLineItemResponse,
    InvoiceOrganizationSummary,
    InvoiceResponse,
    InvoiceSummaryResponse,
    InvoiceUpdate,
)
from app.services.audit import log_audit_event
from app.services.email import build_invoice_email
from app.services.jobs import enqueue_email
from app.services.notifications import create_notification
from app.services.pdf import generate_invoice_pdf
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/invoices", tags=["invoices"])
ALLOWED = ["partner", "admin", "lawyer", "paralegal"]
ALLOWED_PAY = ["partner", "admin", "lawyer"]
VALID_STATUS = {"draft", "sent", "paid", "overdue", "cancelled"}


def line_ser(li: InvoiceLineItem) -> InvoiceLineItemResponse:
    return InvoiceLineItemResponse(**{c: getattr(li, c) for c in InvoiceLineItemResponse.model_fields.keys()})


def org_ser(org: Organization | None) -> InvoiceOrganizationSummary:
    return InvoiceOrganizationSummary(
        id=getattr(org, "id", 0),
        name=getattr(org, "name", None) or "Firm",
        address=getattr(org, "address", None),
        email=getattr(org, "email", None),
        phone=getattr(org, "phone", None),
        tax_number=getattr(org, "tax_number", None) or getattr(org, "trn_no", None) or getattr(org, "vat_number", None),
    )


def client_ser(client: Client | None, fallback_id: int) -> InvoiceClientSummary:
    return InvoiceClientSummary(
        id=getattr(client, "id", fallback_id),
        name=getattr(client, "name", None) or f"Client #{fallback_id}",
        email=getattr(client, "email", None),
        phone=getattr(client, "phone", None),
        address=getattr(client, "address", None),
        occupation=getattr(client, "occupation", None),
        tax_number=getattr(client, "trn_no", None),
    )


def inv_ser(i: Invoice) -> InvoiceResponse:
    base = {
        c: getattr(i, c)
        for c in InvoiceResponse.model_fields.keys()
        if c not in {"line_items", "organization", "client"}
    }
    return InvoiceResponse(
        **base,
        organization=org_ser(getattr(i, "organization", None)),
        client=client_ser(getattr(i, "client", None), i.client_id),
        line_items=[line_ser(x) for x in i.line_items],
    )


async def get_invoice_or_404(db: AsyncSession, org_id: int, invoice_id: int) -> Invoice:
    inv = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.organization_id == org_id)
        .options(
            selectinload(Invoice.line_items),
            selectinload(Invoice.client),
            selectinload(Invoice.organization),
        )
    )
    if not inv: raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


async def validate_client_case(db: AsyncSession, org_id: int, client_id: int, case_id: int | None):
    client = await db.scalar(select(Client).where(Client.id == client_id, Client.organization_id == org_id))
    if not client: raise HTTPException(status_code=400, detail="Client must belong to your organization")
    case = None
    if case_id is not None:
        case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == org_id))
        if not case: raise HTTPException(status_code=400, detail="Case must belong to your organization")
        if case.client_id != client_id: raise HTTPException(status_code=400, detail="Case does not belong to client")
    return client, case


async def next_invoice_number(db: AsyncSession, org_id: int) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"INV-{year}-"
    count = await db.scalar(select(func.count(Invoice.id)).where(Invoice.organization_id == org_id, Invoice.invoice_number.like(f"{prefix}%")))
    return f"{prefix}{int(count or 0)+1:04d}"


def recalc(invoice: Invoice):
    subtotal = sum((li.amount for li in invoice.line_items), Decimal("0"))
    invoice.subtotal = subtotal
    invoice.total = subtotal + (invoice.tax_amount or Decimal("0"))
    if invoice.paid_amount is None:
        invoice.paid_amount = Decimal("0")
    invoice.balance_due = max(Decimal("0"), invoice.total - invoice.paid_amount)


@router.post("", response_model=InvoiceResponse)
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    _, case = await validate_client_case(db, current_user.organization_id, payload.client_id, payload.case_id)
    now = datetime.now(timezone.utc)
    inv = Invoice(
        organization_id=current_user.organization_id,
        client_id=payload.client_id,
        case_id=payload.case_id,
        invoice_number=await next_invoice_number(db, current_user.organization_id),
        status="draft",
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal("0"),
        paid_amount=Decimal("0"),
        balance_due=Decimal("0"),
        notes=payload.notes,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(inv); await db.flush()
    recalc(inv)
    if case:
        await create_case_timeline_event(db, organization_id=current_user.organization_id, case_id=case.id, actor_id=current_user.id, event_type="invoice_created", title=f"Invoice created: {inv.invoice_number}", metadata_json={"invoice_id": inv.id})
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, inv.id)
    return inv_ser(inv)


@router.post("/generate-from-case/{case_id}", response_model=InvoiceResponse)
async def generate_from_case(case_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == current_user.organization_id))
    if not case: raise HTTPException(status_code=404, detail="Case not found")
    now = datetime.now(timezone.utc)
    inv = Invoice(
        organization_id=current_user.organization_id, client_id=case.client_id, case_id=case.id,
        invoice_number=await next_invoice_number(db, current_user.organization_id), status="draft",
        issue_date=date.today(), due_date=None, subtotal=Decimal("0"), tax_amount=Decimal("0"), total=Decimal("0"),
        paid_amount=Decimal("0"), balance_due=Decimal("0"), notes="Generated from case", created_by=current_user.id, created_at=now, updated_at=now,
    )
    db.add(inv); await db.flush()

    tes = (await db.scalars(select(TimeEntry).where(TimeEntry.organization_id == current_user.organization_id, TimeEntry.case_id == case.id, TimeEntry.billable == True, TimeEntry.billed == False))).all()
    exs = (await db.scalars(select(Expense).where(Expense.organization_id == current_user.organization_id, Expense.case_id == case.id, Expense.billable == True, Expense.billed == False))).all()

    for te in tes:
        amt = (te.hours or Decimal("0")) * (te.rate or Decimal("0"))
        db.add(InvoiceLineItem(organization_id=current_user.organization_id, invoice_id=inv.id, line_type="time", description=te.description, quantity=te.hours, unit_price=te.rate, amount=amt, time_entry_id=te.id, expense_id=None, created_at=now))
    for ex in exs:
        db.add(InvoiceLineItem(organization_id=current_user.organization_id, invoice_id=inv.id, line_type="expense", description=ex.description, quantity=Decimal("1"), unit_price=ex.amount, amount=ex.amount, time_entry_id=None, expense_id=ex.id, created_at=now))

    await db.flush(); inv = await get_invoice_or_404(db, current_user.organization_id, inv.id)
    recalc(inv); inv.updated_at = now
    await create_case_timeline_event(db, organization_id=current_user.organization_id, case_id=case.id, actor_id=current_user.id, event_type="invoice_created", title=f"Invoice created: {inv.invoice_number}", metadata_json={"invoice_id": inv.id, "time_entries": len(tes), "expenses": len(exs)})
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, inv.id)
    return inv_ser(inv)


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    rows = await db.scalars(
        select(Invoice)
        .where(Invoice.organization_id == current_user.organization_id)
        .options(
            selectinload(Invoice.line_items),
            selectinload(Invoice.client),
            selectinload(Invoice.organization),
        )
        .order_by(Invoice.created_at.desc())
    )
    return [inv_ser(i) for i in rows.all()]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    return inv_ser(await get_invoice_or_404(db, current_user.organization_id, invoice_id))


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.client:
        client = await db.scalar(select(Client).where(Client.organization_id == current_user.organization_id, Client.user_id == current_user.id))
        if not client:
            raise HTTPException(status_code=403, detail="Client profile not linked")
        inv = await db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == current_user.organization_id))
        if not inv or inv.client_id != client.id:
            raise HTTPException(status_code=404, detail="Invoice not found")
        generated = await generate_invoice_pdf(invoice_id, db=db, organization_id=current_user.organization_id)
    elif current_user.role.value in ALLOWED:
        await get_invoice_or_404(db, current_user.organization_id, invoice_id)
        generated = await generate_invoice_pdf(invoice_id, db=db, organization_id=current_user.organization_id)
    else:
        raise HTTPException(status_code=403, detail="Insufficient role")

    file_path = Path(generated.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Generated PDF file not found")
    return FileResponse(path=str(file_path), filename=generated.filename, media_type="application/pdf")


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(invoice_id: int, payload: InvoiceUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    updates = payload.model_dump(exclude_unset=True)
    st = updates.get("status")
    if st and st not in VALID_STATUS: raise HTTPException(status_code=400, detail="Invalid invoice status")
    for k, v in updates.items(): setattr(inv, k, v)
    recalc(inv); inv.updated_at = datetime.now(timezone.utc)
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    return inv_ser(inv)


@router.patch("/{invoice_id}/mark-sent", response_model=InvoiceResponse)
async def mark_sent(invoice_id: int, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    inv.status = "sent"; inv.updated_at = datetime.now(timezone.utc)
    linked_te_ids = [li.time_entry_id for li in inv.line_items if li.time_entry_id]
    linked_ex_ids = [li.expense_id for li in inv.line_items if li.expense_id]
    if linked_te_ids:
        entries = (await db.scalars(select(TimeEntry).where(TimeEntry.organization_id == current_user.organization_id, TimeEntry.id.in_(linked_te_ids)))).all()
        for e in entries: e.billed = True
    if linked_ex_ids:
        expenses = (await db.scalars(select(Expense).where(Expense.organization_id == current_user.organization_id, Expense.id.in_(linked_ex_ids)))).all()
        for e in expenses: e.billed = True
    if inv.case_id:
        await create_case_timeline_event(db, organization_id=current_user.organization_id, case_id=inv.case_id, actor_id=current_user.id, event_type="invoice_sent", title=f"Invoice sent: {inv.invoice_number}", metadata_json={"invoice_id": inv.id})
    client = await db.scalar(select(Client).where(Client.id == inv.client_id, Client.organization_id == current_user.organization_id))
    if client and client.user_id:
        await create_notification(
            db,
            organization_id=current_user.organization_id,
            user_id=client.user_id,
            type="invoice_sent",
            title=f"Invoice sent: {inv.invoice_number}",
            body="A new invoice has been sent to your client portal.",
            metadata_json={"invoice_id": inv.id, "case_id": inv.case_id},
        )
        if client.email:
            subject, html_body, text_body = build_invoice_email(
                client_name=client.name or "Client",
                invoice_number=inv.invoice_number,
                invoice_id=inv.id,
            )
            enqueue_email(background_tasks, to_email=client.email, subject=subject, html_body=html_body, text_body=text_body)
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="invoice_sent",
        entity_type="invoice",
        entity_id=str(inv.id),
        description=f"Invoice sent: {inv.invoice_number}",
        metadata_json={"case_id": inv.case_id, "client_id": inv.client_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    return inv_ser(inv)


@router.patch("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_paid(invoice_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED_PAY))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    inv.status = "paid"
    inv.paid_amount = inv.total
    inv.balance_due = Decimal("0")
    inv.updated_at = datetime.now(timezone.utc)
    if inv.case_id:
        await create_case_timeline_event(db, organization_id=current_user.organization_id, case_id=inv.case_id, actor_id=current_user.id, event_type="invoice_paid", title=f"Invoice paid: {inv.invoice_number}", metadata_json={"invoice_id": inv.id})
    await log_audit_event(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="invoice_paid",
        entity_type="invoice",
        entity_id=str(inv.id),
        description=f"Invoice paid: {inv.invoice_number}",
        metadata_json={"case_id": inv.case_id, "client_id": inv.client_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    return inv_ser(inv)


@router.get("/{invoice_id}/summary", response_model=InvoiceSummaryResponse)
async def summary(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    return InvoiceSummaryResponse(invoice_id=inv.id, invoice_number=inv.invoice_number, status=inv.status, subtotal=inv.subtotal, tax_amount=inv.tax_amount, total=inv.total, paid_amount=inv.paid_amount, balance_due=inv.balance_due, line_items_count=len(inv.line_items))


@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    await db.delete(inv); await db.commit(); return {"ok": True}
