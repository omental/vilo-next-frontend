from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - registers the complete model metadata
from app.api import deps as deps_module
from app.db.base import Base
from app.main import app
from app.models.client import Client
from app.models.case import Case
from app.models.enums import RecordStatus, UserRole
from app.models.expense import Expense
from app.models.firm_payment_account import FirmPaymentAccount
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.invoice_payment import InvoicePayment
from app.models.organization import Organization
from app.models.time_entry import TimeEntry
from app.models.user import User


@pytest_asyncio.fixture
async def invoice_async_client(tmp_path):
    database_path = tmp_path / "invoice-regression.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        tables = [
            Organization.__table__,
            User.__table__,
            Client.__table__,
            Case.__table__,
            FirmPaymentAccount.__table__,
            Invoice.__table__,
            TimeEntry.__table__,
            Expense.__table__,
            InvoiceLineItem.__table__,
            InvoicePayment.__table__,
        ]
        await connection.run_sync(lambda sync_connection: Base.metadata.create_all(sync_connection, tables=tables))

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        organization = Organization(
            name="Async Test Firm",
            slug="async-test-firm",
            status=RecordStatus.active,
            invoice_tax_label="GCT",
            invoice_tax_rate=Decimal("0.00"),
            created_at=now,
            updated_at=now,
        )
        session.add(organization)
        await session.flush()
        user = User(
            organization_id=organization.id,
            name="Async Partner",
            email="async-partner@example.com",
            hashed_password="not-used",
            role=UserRole.partner,
            status=RecordStatus.active,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.flush()
        client = Client(
            organization_id=organization.id,
            name="Production Path Client",
            client_type="individual",
            billing_currency="JMD",
            created_at=now,
            updated_at=now,
        )
        account = FirmPaymentAccount(
            organization_id=organization.id,
            account_name="Default JMD Operating",
            bank_name="Test Bank",
            account_number="12345",
            currency="JMD",
            is_default=True,
            is_active=True,
            created_by_id=user.id,
            created_at=now,
            updated_at=now,
        )
        session.add_all([client, account])
        await session.commit()
        user_id = user.id
        organization_id = organization.id
        client_id = client.id

    async def _get_db():
        async with session_factory() as session:
            yield session

    async def _get_current_user():
        async with session_factory() as session:
            return await session.get(User, user_id)

    app.dependency_overrides[deps_module.get_db] = _get_db
    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client_http:
            yield client_http, session_factory, organization_id, client_id
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


def _create_payload(client_id: int, **overrides):
    payload = {
        "client_id": client_id,
        "currency": "JMD",
        "issue_date": "2026-07-24",
        "line_items": [
            {
                "line_type": "legal_fee",
                "description": "Production path legal work",
                "quantity": "2.00",
                "unit_price": "7500.00",
                "amount": "15000.00",
            }
        ],
        "subtotal": "15000.00",
        "tax_amount": "0.00",
        "total": "15000.00",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_real_async_create_update_and_rollback_paths(invoice_async_client):
    client_http, session_factory, organization_id, client_id = invoice_async_client

    created = await client_http.post("/api/v1/invoices", json=_create_payload(client_id))
    assert created.status_code == 200, created.text
    created_body = created.json()
    invoice_id = created_body["id"]
    assert created_body["currency"] == "JMD"
    assert created_body["subtotal"] == "15000.00"
    assert created_body["tax_amount"] == "0.00"
    assert created_body["total"] == "15000.00"
    assert len(created_body["line_items"]) == 1

    async with session_factory() as session:
        invoice = await session.get(Invoice, invoice_id)
        rows = (
            await session.scalars(
                select(InvoiceLineItem).where(
                    InvoiceLineItem.organization_id == organization_id,
                    InvoiceLineItem.invoice_id == invoice_id,
                )
            )
        ).all()
        assert invoice is not None
        assert len(rows) == 1
        assert rows[0].quantity == Decimal("2.00")
        assert rows[0].unit_price == Decimal("7500.00")
        assert rows[0].amount == Decimal("15000.00")

    updated = await client_http.patch(
        f"/api/v1/invoices/{invoice_id}",
        json={
            "line_items": [
                {
                    "line_type": "flat_fee",
                    "description": "Replacement fixed fee",
                    "quantity": "1.00",
                    "unit_price": "9000.00",
                    "amount": "9000.00",
                },
                {
                    "line_type": "expense",
                    "description": "Replacement filing cost",
                    "quantity": "1.00",
                    "unit_price": "1000.00",
                    "amount": "1000.00",
                },
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    updated_body = updated.json()
    assert updated_body["subtotal"] == "10000.00"
    assert updated_body["total"] == "10000.00"
    assert len(updated_body["line_items"]) == 2

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(InvoiceLineItem)
                .where(
                    InvoiceLineItem.organization_id == organization_id,
                    InvoiceLineItem.invoice_id == invoice_id,
                )
                .order_by(InvoiceLineItem.id)
            )
        ).all()
        assert len(rows) == 2
        assert [row.amount for row in rows] == [Decimal("9000.00"), Decimal("1000.00")]

    failed_update = await client_http.patch(
        f"/api/v1/invoices/{invoice_id}",
        json={
            "line_items": [
                {
                    "line_type": "legal_fee",
                    "description": "Invalid staff reference",
                    "quantity": "1.00",
                    "unit_price": "500.00",
                    "amount": "500.00",
                    "staff_user_id": 999999,
                }
            ]
        },
    )
    assert failed_update.status_code == 500
    assert failed_update.json() == {
        "detail": "Invoice could not be processed because of a server error."
    }

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(InvoiceLineItem)
                .where(
                    InvoiceLineItem.organization_id == organization_id,
                    InvoiceLineItem.invoice_id == invoice_id,
                )
                .order_by(InvoiceLineItem.id)
            )
        ).all()
        assert len(rows) == 2
        assert [row.amount for row in rows] == [Decimal("9000.00"), Decimal("1000.00")]

    failed_create = await client_http.post(
        "/api/v1/invoices",
        json=_create_payload(
            client_id,
            line_items=[
                {
                    "line_type": "hourly_work",
                    "description": "Missing time entry",
                    "time_entry_id": 999999,
                }
            ],
            subtotal="0.00",
            total="0.00",
        ),
    )
    assert failed_create.status_code == 400
    assert failed_create.json()["errors"][0]["field"] == "line_items"

    async with session_factory() as session:
        invoice_count = await session.scalar(
            select(func.count(Invoice.id)).where(Invoice.organization_id == organization_id)
        )
        line_count = await session.scalar(
            select(func.count(InvoiceLineItem.id)).where(
                InvoiceLineItem.organization_id == organization_id
            )
        )
        assert invoice_count == 1
        assert line_count == 2
