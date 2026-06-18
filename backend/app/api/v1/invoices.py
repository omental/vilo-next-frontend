from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
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
    InvoiceApplyTrustRequest,
    InvoiceCreate,
    InvoiceLineItemCreate,
    InvoiceLineItemResponse,
    InvoicePaymentAccountSummary,
    InvoicePaymentResponse,
    InvoicePaymentSummaryResponse,
    InvoicePaymentVoidRequest,
    InvoicePaymentVoidResponse,
    InvoiceOrganizationSummary,
    InvoiceResponse,
    InvoiceSummaryResponse,
    InvoiceTrustApplyResponse,
    InvoiceUpdate,
)
from app.services.audit import log_audit_event
from app.services.billing import resolve_invoice_payment_account, validate_time_entry_invoice_link
from app.services.email import build_invoice_email
from app.services.finance import (
    apply_trust_to_invoice,
    create_invoice_payment_operating_transaction,
    derive_invoice_status,
    get_invoice_currency,
    get_matter_trust_balance,
    summarize_invoice_payment_method,
    money,
    normalize_currency,
    void_invoice_payment,
    validate_invoice_line_type,
)
from app.services.jobs import enqueue_email
from app.services.notifications import create_notification
from app.services.pdf import generate_invoice_pdf
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/invoices", tags=["invoices"])
ALLOWED = ["partner", "admin", "lawyer", "paralegal"]
ALLOWED_PAY = ["partner", "admin"]
VALID_STATUS = {"draft", "sent", "partially_paid", "paid", "overdue", "cancelled"}


def line_ser(li: InvoiceLineItem) -> InvoiceLineItemResponse:
    return InvoiceLineItemResponse(**{c: getattr(li, c, None) for c in InvoiceLineItemResponse.model_fields.keys()})


def payment_ser(payment) -> InvoicePaymentResponse:
    return InvoicePaymentResponse(
        id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        payment_method=getattr(payment, "payment_method", None),
        payment_source=payment.payment_source,
        paid_at=payment.paid_at,
        reference_number=getattr(payment, "reference_number", None),
        description=getattr(payment, "description", None),
        linked_trust_transaction_id=getattr(payment, "linked_trust_transaction_id", None),
        linked_operating_transaction_id=getattr(payment, "linked_operating_transaction_id", None),
        created_by_id=payment.created_by_id,
        created_at=payment.created_at,
        voided_at=getattr(payment, "voided_at", None),
        voided_by_id=getattr(payment, "voided_by_id", None),
        void_reason=getattr(payment, "void_reason", None),
    )


def payment_account_ser(account) -> InvoicePaymentAccountSummary | None:
    if not account:
        return None
    return InvoicePaymentAccountSummary(
        id=account.id,
        account_name=account.account_name,
        bank_name=account.bank_name,
        account_number=account.account_number,
        currency=account.currency,
        swift_routing=getattr(account, "swift_routing", None),
        notes=getattr(account, "notes", None),
        payment_instructions=getattr(account, "payment_instructions", None),
    )


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


def inv_ser(i: Invoice, *, trust_balance_available: Decimal | None = None) -> InvoiceResponse:
    display_status = derive_invoice_status(i)
    base = {
        c: getattr(i, c, None)
        for c in InvoiceResponse.model_fields.keys()
        if c not in {"line_items", "organization", "client", "payments", "payment_account", "trust_balance_available", "can_apply_trust", "display_status", "payment_method_summary", "matter_title"}
    }
    return InvoiceResponse(
        **base,
        display_status=display_status,
        payment_method_summary=summarize_invoice_payment_method(i),
        organization=org_ser(getattr(i, "organization", None)),
        client=client_ser(getattr(i, "client", None), i.client_id),
        payment_account=payment_account_ser(getattr(i, "payment_account", None)),
        matter_title=getattr(getattr(i, "case", None), "title", None),
        line_items=[line_ser(x) for x in i.line_items],
        payments=[payment_ser(x) for x in getattr(i, "payments", [])],
        trust_balance_available=trust_balance_available,
        can_apply_trust=bool(i.case_id and i.balance_due > 0 and display_status not in {"paid", "cancelled"}),
    )


async def get_invoice_or_404(db: AsyncSession, org_id: int, invoice_id: int) -> Invoice:
    inv = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.organization_id == org_id)
        .options(
            selectinload(Invoice.line_items).selectinload(InvoiceLineItem.time_entry).selectinload(TimeEntry.user),
            selectinload(Invoice.line_items).selectinload(InvoiceLineItem.staff_user),
            selectinload(Invoice.client),
            selectinload(Invoice.organization),
            selectinload(Invoice.case),
            selectinload(Invoice.payment_account),
            selectinload(Invoice.payments),
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


async def resolve_invoice_number(db: AsyncSession, org_id: int, requested: str | None, *, exclude_invoice_id: int | None = None) -> str:
    candidate = (requested or "").strip() or await next_invoice_number(db, org_id)
    query = select(Invoice.id).where(Invoice.organization_id == org_id, Invoice.invoice_number == candidate)
    if exclude_invoice_id is not None:
        query = query.where(Invoice.id != exclude_invoice_id)
    existing = await db.scalar(query)
    if existing is not None:
        raise HTTPException(status_code=400, detail="Invoice number already exists")
    return candidate


def recalc(invoice: Invoice):
    subtotal = sum((li.amount for li in invoice.line_items), Decimal("0"))
    invoice.subtotal = subtotal
    invoice.total = subtotal + (invoice.tax_amount or Decimal("0"))
    if invoice.paid_amount is None:
        invoice.paid_amount = Decimal("0")
    invoice.balance_due = max(Decimal("0"), invoice.total - invoice.paid_amount)


async def sync_invoice_line_items(
    db: AsyncSession,
    *,
    invoice: Invoice,
    organization_id: int,
    line_items: list[InvoiceLineItemCreate],
    created_at: datetime,
) -> None:
    previous_time_entries = (
        await db.scalars(
            select(TimeEntry).where(
                TimeEntry.organization_id == organization_id,
                TimeEntry.invoice_id == invoice.id,
            )
        )
    ).all()
    for time_entry in previous_time_entries:
        time_entry.invoice_id = None
        if time_entry.status == "invoiced":
            time_entry.status = "billable"
        if time_entry.billing_type == "invoiced":
            time_entry.billing_type = "professional_fee"

    invoice.line_items.clear()
    await db.flush()
    for item in line_items:
        quantity = Decimal(str(item.quantity or 0))
        unit_price = Decimal(str(item.unit_price or 0))
        amount = Decimal(str(item.amount)) if item.amount is not None else (quantity * unit_price)
        time_entry_id = None
        staff_user_id = item.staff_user_id
        hours = Decimal(str(item.hours or 0)) if item.hours is not None else None
        rate = Decimal(str(item.rate or 0)) if item.rate is not None else None
        description = item.description.strip()
        line_type = validate_invoice_line_type(item.line_type)

        if item.time_entry_id is not None:
            time_entry = await validate_time_entry_invoice_link(
                db,
                organization_id=organization_id,
                invoice=invoice,
                time_entry_id=item.time_entry_id,
            )
            quantity = _round_quantity(time_entry.duration_minutes)
            unit_price = money(time_entry.hourly_rate)
            amount = money(quantity * unit_price)
            hours = quantity
            rate = unit_price
            staff_user_id = time_entry.user_id
            description = item.description.strip() or time_entry.description or "Time entry"
            line_type = validate_invoice_line_type(item.line_type if item.line_type else "hourly_work")
            time_entry_id = time_entry.id
            time_entry.invoice_id = invoice.id
            time_entry.status = "invoiced"
            time_entry.billing_type = "invoiced"

        invoice.line_items.append(
            InvoiceLineItem(
                organization_id=organization_id,
                invoice_id=invoice.id,
                line_type=line_type,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                amount=money(amount),
                hours=hours,
                rate=rate,
                time_entry_id=time_entry_id,
                expense_id=None,
                staff_user_id=staff_user_id,
                created_at=created_at,
            )
        )


def _round_quantity(duration_minutes: int | None) -> Decimal:
    if not duration_minutes:
        return Decimal("0.00")
    return (Decimal(duration_minutes) / Decimal("60")).quantize(Decimal("0.01"))


@router.post("", response_model=InvoiceResponse)
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    _, case = await validate_client_case(db, current_user.organization_id, payload.client_id, payload.case_id)
    currency = normalize_currency(payload.currency)
    payment_account = await resolve_invoice_payment_account(
        db,
        organization_id=current_user.organization_id,
        currency=currency,
        payment_account_id=payload.payment_account_id,
    )
    now = datetime.now(timezone.utc)
    inv = Invoice(
        organization_id=current_user.organization_id,
        client_id=payload.client_id,
        case_id=payload.case_id,
        invoice_number=await resolve_invoice_number(db, current_user.organization_id, payload.invoice_number),
        currency=currency,
        status="draft",
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        subtotal=Decimal("0"),
        tax_amount=payload.tax_amount,
        total=Decimal("0"),
        paid_amount=Decimal("0"),
        balance_due=Decimal("0"),
        notes=payload.notes,
        payment_instructions=payload.payment_instructions or payment_account.payment_instructions,
        payment_account_id=payment_account.id,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(inv); await db.flush()
    await sync_invoice_line_items(
        db,
        invoice=inv,
        organization_id=current_user.organization_id,
        line_items=payload.line_items,
        created_at=now,
    )
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
    payment_account = await resolve_invoice_payment_account(
        db,
        organization_id=current_user.organization_id,
        currency="USD",
        payment_account_id=None,
    )
    inv = Invoice(
        organization_id=current_user.organization_id, client_id=case.client_id, case_id=case.id,
        invoice_number=await next_invoice_number(db, current_user.organization_id), currency="USD", status="draft",
        issue_date=date.today(), due_date=None, subtotal=Decimal("0"), tax_amount=Decimal("0"), total=Decimal("0"),
        paid_amount=Decimal("0"), balance_due=Decimal("0"), notes="Generated from case", payment_instructions=payment_account.payment_instructions, payment_account_id=payment_account.id, created_by=current_user.id, created_at=now, updated_at=now,
    )
    db.add(inv); await db.flush()

    tes = (await db.scalars(
        select(TimeEntry).where(
            TimeEntry.organization_id == current_user.organization_id,
            TimeEntry.case_id == case.id,
            TimeEntry.status == "billable",
            TimeEntry.invoice_id.is_(None),
        )
    )).all()
    exs = (await db.scalars(select(Expense).where(Expense.organization_id == current_user.organization_id, Expense.case_id == case.id, Expense.billable == True, Expense.billed == False))).all()

    for te in tes:
        qty = _round_quantity(te.duration_minutes)
        amt = te.amount or Decimal("0")
        db.add(InvoiceLineItem(organization_id=current_user.organization_id, invoice_id=inv.id, line_type=validate_invoice_line_type("legal_fee"), description=te.description or "Time entry", quantity=qty, unit_price=te.hourly_rate or Decimal("0"), amount=amt, hours=qty, rate=te.hourly_rate or Decimal("0"), time_entry_id=te.id, expense_id=None, staff_user_id=te.user_id, created_at=now))
        te.invoice_id = inv.id
        te.status = "invoiced"
        te.billing_type = "invoiced"
    for ex in exs:
        db.add(InvoiceLineItem(organization_id=current_user.organization_id, invoice_id=inv.id, line_type=validate_invoice_line_type("expense"), description=ex.description, quantity=Decimal("1"), unit_price=ex.amount, amount=ex.amount, time_entry_id=None, expense_id=ex.id, created_at=now))

    await db.flush(); inv = await get_invoice_or_404(db, current_user.organization_id, inv.id)
    recalc(inv); inv.updated_at = now
    await create_case_timeline_event(db, organization_id=current_user.organization_id, case_id=case.id, actor_id=current_user.id, event_type="invoice_created", title=f"Invoice created: {inv.invoice_number}", metadata_json={"invoice_id": inv.id, "time_entries": len(tes), "expenses": len(exs)})
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, inv.id)
    return inv_ser(inv)


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    client_id: int | None = Query(default=None),
    case_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED)),
):
    query = select(Invoice).where(Invoice.organization_id == current_user.organization_id)
    if client_id is not None:
        query = query.where(Invoice.client_id == client_id)
    if case_id is not None:
        query = query.where(Invoice.case_id == case_id)
    rows = await db.scalars(
        query
        .options(
            selectinload(Invoice.line_items).selectinload(InvoiceLineItem.time_entry).selectinload(TimeEntry.user),
            selectinload(Invoice.line_items).selectinload(InvoiceLineItem.staff_user),
            selectinload(Invoice.client),
            selectinload(Invoice.organization),
            selectinload(Invoice.case),
            selectinload(Invoice.payment_account),
            selectinload(Invoice.payments),
        )
        .order_by(Invoice.created_at.desc())
    )
    return [inv_ser(i) for i in rows.all()]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    trust_balance = Decimal("0.00")
    if inv.case_id is not None:
        trust_balance = await get_matter_trust_balance(db, current_user.organization_id, inv.case_id, await get_invoice_currency(db, current_user.organization_id, inv))
    return inv_ser(inv, trust_balance_available=trust_balance)


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
    next_client_id = updates["client_id"] if "client_id" in updates else inv.client_id
    next_case_id = updates["case_id"] if "case_id" in updates else inv.case_id
    next_currency = normalize_currency(updates["currency"]) if "currency" in updates and updates["currency"] is not None else inv.currency
    if next_case_id is None:
        raise HTTPException(status_code=400, detail="Invoice must be linked to a matter")
    await validate_client_case(db, current_user.organization_id, next_client_id, next_case_id)
    payment_account = await resolve_invoice_payment_account(
        db,
        organization_id=current_user.organization_id,
        currency=next_currency,
        payment_account_id=updates.get("payment_account_id", inv.payment_account_id),
    )
    if "invoice_number" in updates:
        inv.invoice_number = await resolve_invoice_number(db, current_user.organization_id, updates["invoice_number"], exclude_invoice_id=inv.id)
    for k, v in updates.items():
        if k in {"invoice_number", "line_items"}:
            continue
        setattr(inv, k, v)
    account_changed = payment_account.id != inv.payment_account_id or next_currency != inv.currency
    inv.currency = next_currency
    inv.payment_account_id = payment_account.id
    if "payment_instructions" not in updates and account_changed and not inv.payment_instructions:
        inv.payment_instructions = payment_account.payment_instructions
    if "line_items" in updates and updates["line_items"] is not None:
        await sync_invoice_line_items(
            db,
            invoice=inv,
            organization_id=current_user.organization_id,
            line_items=payload.line_items or [],
            created_at=datetime.now(timezone.utc),
        )
    recalc(inv); inv.updated_at = datetime.now(timezone.utc)
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    return inv_ser(inv)


@router.patch("/{invoice_id}/mark-sent", response_model=InvoiceResponse)
async def mark_sent(invoice_id: int, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    if inv.case_id is None:
        raise HTTPException(status_code=400, detail="Invoice must be linked to a matter")
    inv.status = "sent"; inv.updated_at = datetime.now(timezone.utc)
    linked_te_ids = [li.time_entry_id for li in inv.line_items if li.time_entry_id]
    linked_ex_ids = [li.expense_id for li in inv.line_items if li.expense_id]
    if linked_te_ids:
        entries = (await db.scalars(select(TimeEntry).where(TimeEntry.organization_id == current_user.organization_id, TimeEntry.id.in_(linked_te_ids)))).all()
        for e in entries:
            e.invoice_id = inv.id
            e.status = "invoiced"
            e.billing_type = "invoiced"
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
    operating_txn, payment = await create_invoice_payment_operating_transaction(
        db,
        organization_id=current_user.organization_id,
        invoice=inv,
        created_by_id=current_user.id,
        transaction_date=date.today(),
    )
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
        metadata_json={"case_id": inv.case_id, "client_id": inv.client_id, "payment_id": payment.id, "operating_transaction_id": operating_txn.id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit(); inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    return inv_ser(inv)


@router.post("/{invoice_id}/apply-trust", response_model=InvoiceTrustApplyResponse)
async def apply_trust(
    invoice_id: int,
    payload: InvoiceApplyTrustRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_PAY)),
):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    inv, payment, trust_txn, operating_txn = await apply_trust_to_invoice(
        db,
        organization_id=current_user.organization_id,
        invoice=inv,
        amount=payload.amount,
        created_by_id=current_user.id,
        trust_account_id=payload.trust_account_id,
        currency=payload.currency,
        description=payload.description,
        reference_number=payload.reference_number,
        payment_date=payload.payment_date,
        audit_request={
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    await db.commit()
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    trust_balance = Decimal("0.00")
    if inv.case_id is not None:
        trust_balance = await get_matter_trust_balance(db, current_user.organization_id, inv.case_id, await get_invoice_currency(db, current_user.organization_id, inv, payload.currency))
    return InvoiceTrustApplyResponse(
        invoice=inv_ser(inv, trust_balance_available=trust_balance),
        payment=payment_ser(payment),
        trust_transaction_id=trust_txn.id,
        operating_transaction_id=operating_txn.id,
    )


@router.post("/{invoice_id}/payments/{payment_id}/void", response_model=InvoicePaymentVoidResponse)
async def void_payment(
    invoice_id: int,
    payment_id: int,
    payload: InvoicePaymentVoidRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_PAY)),
):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    payment, reversal_operating_txn, reversal_trust_txn = await void_invoice_payment(
        db,
        organization_id=current_user.organization_id,
        invoice=inv,
        payment_id=payment_id,
        void_reason=payload.void_reason,
        voided_by_id=current_user.id,
        void_date=payload.void_date,
        description=payload.description,
        audit_request={
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    await db.commit()
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    trust_balance = Decimal("0.00")
    if inv.case_id is not None:
        trust_balance = await get_matter_trust_balance(db, current_user.organization_id, inv.case_id, await get_invoice_currency(db, current_user.organization_id, inv, payment.currency))
    return InvoicePaymentVoidResponse(
        invoice=inv_ser(inv, trust_balance_available=trust_balance),
        payment=payment_ser(payment),
        reversal_operating_transaction_id=reversal_operating_txn.id,
        reversal_trust_transaction_id=reversal_trust_txn.id if reversal_trust_txn else None,
    )


@router.get("/{invoice_id}/payment-summary", response_model=InvoicePaymentSummaryResponse)
async def payment_summary(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    trust_balance = Decimal("0.00")
    if inv.case_id is not None:
        trust_balance = await get_matter_trust_balance(db, current_user.organization_id, inv.case_id, await get_invoice_currency(db, current_user.organization_id, inv))
    return InvoicePaymentSummaryResponse(
        invoice_id=inv.id,
        invoice_number=inv.invoice_number,
        total=inv.total,
        paid_amount=inv.paid_amount,
        balance_due=inv.balance_due,
        trust_balance_available=trust_balance,
        can_apply_trust=bool(inv.case_id and inv.balance_due > 0 and derive_invoice_status(inv) not in {"paid", "cancelled"}),
        payments=[payment_ser(x) for x in getattr(inv, "payments", [])],
    )


@router.get("/{invoice_id}/summary", response_model=InvoiceSummaryResponse)
async def summary(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    return InvoiceSummaryResponse(invoice_id=inv.id, invoice_number=inv.invoice_number, status=inv.status, subtotal=inv.subtotal, tax_amount=inv.tax_amount, total=inv.total, paid_amount=inv.paid_amount, balance_due=inv.balance_due, line_items_count=len(inv.line_items))


@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(role_guard(ALLOWED))):
    inv = await get_invoice_or_404(db, current_user.organization_id, invoice_id)
    await db.delete(inv); await db.commit(); return {"ok": True}
