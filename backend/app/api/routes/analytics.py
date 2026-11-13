"""
Analytics API endpoints.
Provides real-time SQLite metrics, trends, category, priority, status distributions,
and assignment group workload with configurable date filtering.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.session import get_db
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    CategoryDistributionItem,
    PriorityDistributionItem,
    StatusDistributionItem,
    TicketTrendPoint,
    WorkloadItem,
)
from app.services.analytics.service import (
    get_analytics_summary,
    get_category_distribution,
    get_priority_distribution,
    get_status_distribution,
    get_ticket_trends,
    get_workload,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_summary(
    range: Optional[str] = Query("30d", description="7d, 30d, 90d, all, or custom"),
    start_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return top-level KPIs including SLA compliance and average resolution time."""
    return get_analytics_summary(db, date_range=range, start_date=start_date, end_date=end_date)


@router.get("/ticket-trends", response_model=List[TicketTrendPoint])
def get_trends(
    range: Optional[str] = Query("30d", description="7d, 30d, 90d, all, or custom"),
    start_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return daily ticket volume (created, resolved, breached) over time."""
    return get_ticket_trends(db, date_range=range, start_date=start_date, end_date=end_date)


@router.get("/category-distribution", response_model=List[CategoryDistributionItem])
def get_category_dist(
    range: Optional[str] = Query("30d", description="7d, 30d, 90d, all, or custom"),
    start_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return category distribution breakdown and percentages."""
    return get_category_distribution(db, date_range=range, start_date=start_date, end_date=end_date)


@router.get("/priority-distribution", response_model=List[PriorityDistributionItem])
def get_priority_dist(
    range: Optional[str] = Query("30d", description="7d, 30d, 90d, all, or custom"),
    start_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return priority distribution breakdown and percentages."""
    return get_priority_distribution(db, date_range=range, start_date=start_date, end_date=end_date)


@router.get("/status-distribution", response_model=List[StatusDistributionItem])
def get_status_dist(
    range: Optional[str] = Query("30d", description="7d, 30d, 90d, all, or custom"),
    start_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return status distribution breakdown and percentages."""
    return get_status_distribution(db, date_range=range, start_date=start_date, end_date=end_date)


@router.get("/workload", response_model=List[WorkloadItem])
def get_group_workload(
    range: Optional[str] = Query("30d", description="7d, 30d, 90d, all, or custom"),
    start_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO or YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return assignment group workload breakdown."""
    return get_workload(db, date_range=range, start_date=start_date, end_date=end_date)
