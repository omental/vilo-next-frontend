import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.v1 import api_router
from app.db.session import SessionLocal
from app.errors import InvoiceServerError, InvoiceValidationError
from app.services.reminders import REMINDER_POLL_INTERVAL_SECONDS, process_due_reminders


async def _reminder_loop() -> None:
    while True:
        try:
            async with SessionLocal() as db:
                await process_due_reminders(db)
        except Exception:
            # The request-time notification processor is a fallback if the startup loop
            # temporarily cannot reach the database.
            pass
        await asyncio.sleep(REMINDER_POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_reminder_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="VILO API", version="1.0.0", lifespan=lifespan)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(InvoiceValidationError)
async def invoice_validation_exception_handler(request: Request, exc: InvoiceValidationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": "Invoice validation failed", "errors": exc.errors},
    )


@app.exception_handler(InvoiceServerError)
async def invoice_server_exception_handler(request: Request, exc: InvoiceServerError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Invoice could not be processed because of a server error."},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.method == "POST" and request.url.path.rstrip("/") == "/api/v1/invoices":
        errors = []
        for item in exc.errors():
            location = [str(part) for part in item.get("loc", ()) if part not in {"body"}]
            field = ".".join(location) or "invoice"
            error_type = item.get("type", "")
            message = item.get("msg", "Invalid value.")
            if error_type == "missing":
                message = "This field is required."
            elif message.startswith("Value error, "):
                message = message.removeprefix("Value error, ")
            if field == "invoice" and "exactly one of client_id or manual_client_name" in message:
                field = "client_id"
                message = "Select a client or enter a manual invoice recipient, but not both."
            elif field == "invoice" and "Manual invoice recipients cannot be linked to a case" in message:
                field = "case_id"
            elif field == "invoice" and "due_date cannot be before issue_date" in message:
                field = "due_date"
            errors.append({"field": field, "message": message})
        return JSONResponse(
            status_code=422,
            content={"detail": "Invoice validation failed", "errors": errors},
        )
    return await default_request_validation_exception_handler(request, exc)


@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    return Response(status_code=200)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
