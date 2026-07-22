from fastapi import APIRouter

from app.api.v1 import auth, organizations, users, team, clients, cases, tasks, calendar, documents, precedents, case_notes, time_entries, expenses, invoices, trust, accounting, reports, portal, conversations, portal_messages, admin, notifications, audit_logs, settings, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(team.router)
api_router.include_router(clients.router)
api_router.include_router(cases.router)
api_router.include_router(tasks.router)
api_router.include_router(calendar.router)
api_router.include_router(documents.router)
api_router.include_router(precedents.router)
api_router.include_router(case_notes.router)
api_router.include_router(time_entries.router)
api_router.include_router(expenses.router)
api_router.include_router(invoices.router)
api_router.include_router(trust.router)
api_router.include_router(accounting.router)
api_router.include_router(settings.router)
api_router.include_router(reports.router)
api_router.include_router(portal.router)

api_router.include_router(conversations.router)
api_router.include_router(portal_messages.router)
api_router.include_router(notifications.router)
api_router.include_router(audit_logs.router)
api_router.include_router(search.router)

api_router.include_router(admin.router)
