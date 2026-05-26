from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PriorityTimelineItem(BaseModel):
    id: int
    title: str
    type: str
    priority: str
    due_date: datetime | None
    related_case_id: int | None


class TodayOverview(BaseModel):
    due_today_count: int
    overdue_count: int
    unread_messages_count: int
    priority_timeline: list[PriorityTimelineItem]


class CalendarEventItem(BaseModel):
    id: int
    title: str
    type: str
    starts_at: datetime
    time: str
    related_case_id: int | None


class CalendarOverview(BaseModel):
    month: int
    year: int
    upcoming_events: list[CalendarEventItem]


class MonthlyChartPoint(BaseModel):
    month: datetime
    amount: Decimal


class FinancialOverview(BaseModel):
    monthly_revenue: Decimal
    monthly_expenses: Decimal
    net_profit: Decimal
    trust_account_balance: Decimal
    monthly_chart_series: list[MonthlyChartPoint]


class BillingChartItem(BaseModel):
    label: str
    value: Decimal


class BillingOverview(BaseModel):
    paid_total: Decimal
    unpaid_total: Decimal
    draft_total: Decimal
    overdue_total: Decimal
    chart_series: list[BillingChartItem]


class ActiveCaseRow(BaseModel):
    case_id: int
    display_number: str
    client_name: str
    matter: str
    lead: str
    status: str
    due_date: datetime | None


class FirmSnapshot(BaseModel):
    total_cases: int
    active_cases: int
    court_cases: int
    cases_in_court: int
    closed_cases: int
    pending_cases: int
    high_priority_cases: int
    total_tasks: int
    stalled_cases: int
    case_status_percentage: int


class DashboardWidgetsResponse(BaseModel):
    firm_snapshot: FirmSnapshot
    today_overview: TodayOverview
    calendar_overview: CalendarOverview
    financial_overview: FinancialOverview
    billing_overview: BillingOverview
    active_cases: list[ActiveCaseRow]
