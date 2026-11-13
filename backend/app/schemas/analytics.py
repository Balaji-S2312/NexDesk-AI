"""
Pydantic schemas for Service Analytics and Dashboard metrics.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class AnalyticsSummaryResponse(BaseModel):
    total_tickets: int = Field(..., description="Total tickets in filtered scope")
    open_tickets: int = Field(..., description="Tickets currently in open/assigned state")
    in_progress_tickets: int = Field(..., description="Tickets currently in progress or pending")
    resolved_tickets: int = Field(..., description="Tickets resolved or closed")
    sla_breaches: int = Field(..., description="Count of tickets that breached response or resolution SLA")
    avg_resolution_time_hours: float = Field(..., description="Mean resolution time in decimal hours")
    avg_resolution_time_display: str = Field(..., description="Human-readable mean resolution time (e.g. 5h 24m)")
    sla_compliance_rate: float = Field(..., description="Percentage of compliant tickets (0-100)")
    response_compliance_rate: float = Field(..., description="Percentage of tickets meeting response SLA")
    resolution_compliance_rate: float = Field(..., description="Percentage of tickets meeting resolution SLA")
    date_range: str = Field(..., description="Active filter window: 7d, 30d, 90d, all, or custom")
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class TicketTrendPoint(BaseModel):
    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    created: int = 0
    resolved: int = 0
    breached: int = 0


class CategoryDistributionItem(BaseModel):
    category: str
    category_label: str
    count: int
    percentage: float


class PriorityDistributionItem(BaseModel):
    priority: str
    priority_label: str
    count: int
    percentage: float


class StatusDistributionItem(BaseModel):
    status: str
    status_label: str
    count: int
    percentage: float


class WorkloadItem(BaseModel):
    group_id: Optional[int] = None
    group_name: str
    total_tickets: int
    open_tickets: int
    breached_tickets: int
