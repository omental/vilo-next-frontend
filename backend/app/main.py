import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.v1 import api_router
from app.db.session import SessionLocal
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


@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    return Response(status_code=200)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
