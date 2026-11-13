"""
Service Analytics and SLA computation engine.
Queries actual database rows in SQLite, aggregates ticket KPIs,
calculates trends, distributions, workload, and SLA compliance metrics.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.models.assignment_group import AssignmentGroup
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    CategoryDistributionItem,
    PriorityDistributionItem,
    StatusDistributionItem,
    TicketTrendPoint,
    WorkloadItem,
)
from app.schemas.sla import (
    SLAIncidentItem,
    SLAOverviewResponse,
    SLAPolicyMetrics,
    SLAPolicyResponse,
)
from app.services.sla.calculator import (
    ensure_utc,
    evaluate_ticket_sla_status,
    format_duration,
)
from app.services.tickets.rules import DONE_STATUSES, PRIORITY_LABELS


CATEGORY_LABELS: Dict[str, str] = {
    "hardware": "Hardware",
    "software": "Software",
    "network": "Network",
    "access_management": "Access Management",
    "email": "Email",
    "security": "Security",
    "other": "Other",
}

STATUS_LABELS: Dict[str, str] = {
    "open": "Open",
    "assigned": "Assigned",
    "in_progress": "In Progress",
    "pending": "Pending",
    "resolved": "Resolved",
    "closed": "Closed",
}


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        # Try ISO format
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return ensure_utc(dt)
    except Exception:
        pass
    try:
        # Try YYYY-MM-DD
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def resolve_date_window(
    date_range: Optional[str] = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[datetime], Optional[datetime], str]:
    """Resolves start and end UTC timestamps and normalized window label."""
    now = datetime.now(timezone.utc)

    parsed_start = parse_date(start_date)
    parsed_end = parse_date(end_date)
    if parsed_start and parsed_end:
        # End date covers through 23:59:59 if no time was specified
        if parsed_end.hour == 0 and parsed_end.minute == 0:
            parsed_end = parsed_end + timedelta(days=1) - timedelta(microseconds=1)
        return parsed_start, parsed_end, "custom"

    range_key = (date_range or "30d").lower()
    if range_key == "7d":
        return now - timedelta(days=7), now, "7d"
    if range_key == "90d":
        return now - timedelta(days=90), now, "90d"
    if range_key == "all":
        return None, None, "all"

    # Default to 30d
    return now - timedelta(days=30), now, "30d"


def _filter_tickets_by_date(
    db: Session,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> List[Ticket]:
    """Query tickets with eager loaded relationships within date window."""
    query = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.sla_policy),
            joinedload(Ticket.group),
            joinedload(Ticket.requester),
        )
    )
    if start_dt is not None:
        query = query.filter(Ticket.created_at >= start_dt)
    if end_dt is not None:
        query = query.filter(Ticket.created_at <= end_dt)

    return query.order_by(Ticket.created_at.desc()).all()


def get_analytics_summary(
    db: Session,
    date_range: Optional[str] = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> AnalyticsSummaryResponse:
    start_dt, end_dt, window_label = resolve_date_window(date_range, start_date, end_date)
    tickets = _filter_tickets_by_date(db, start_dt, end_dt)

    total = len(tickets)
    open_count = 0
    in_progress_count = 0
    resolved_count = 0
    sla_breaches = 0
    response_breaches = 0
    resolution_breaches = 0
    resolution_durations: List[float] = []

    now = datetime.now(timezone.utc)

    for t in tickets:
        status = (t.status or "open").lower()
        if status in ("open", "assigned"):
            open_count += 1
        elif status in ("in_progress", "pending"):
            in_progress_count += 1
        elif status in DONE_STATUSES:
            resolved_count += 1

        # SLA evaluation
        eval_res = evaluate_ticket_sla_status(t, t.sla_policy, as_of=now)
        if eval_res["response_breached"]:
            response_breaches += 1
        if eval_res["resolution_breached"]:
            resolution_breaches += 1
        if eval_res["response_breached"] or eval_res["resolution_breached"]:
            sla_breaches += 1

        # Resolution duration
        if status in DONE_STATUSES and t.created_at:
            created_utc = ensure_utc(t.created_at)
            resolved_utc = ensure_utc(t.resolved_at) or ensure_utc(t.updated_at) or now
            sec = max(0, (resolved_utc - created_utc).total_seconds())
            resolution_durations.append(sec)

    # Averages
    if resolution_durations:
        avg_sec = sum(resolution_durations) / len(resolution_durations)
        avg_hours = round(avg_sec / 3600.0, 2)
        avg_display = format_duration(int(avg_sec))
    else:
        avg_hours = 0.0
        avg_display = "0m"

    # Compliance percentages
    if total > 0:
        overall_compliance = round(((total - sla_breaches) / total) * 100.0, 1)
        resp_compliance = round(((total - response_breaches) / total) * 100.0, 1)
        res_compliance = round(((total - resolution_breaches) / total) * 100.0, 1)
    else:
        overall_compliance = 100.0
        resp_compliance = 100.0
        res_compliance = 100.0

    return AnalyticsSummaryResponse(
        total_tickets=total,
        open_tickets=open_count,
        in_progress_tickets=in_progress_count,
        resolved_tickets=resolved_count,
        sla_breaches=sla_breaches,
        avg_resolution_time_hours=avg_hours,
        avg_resolution_time_display=avg_display,
        sla_compliance_rate=overall_compliance,
        response_compliance_rate=resp_compliance,
        resolution_compliance_rate=res_compliance,
        date_range=window_label,
        start_date=start_dt.isoformat() if start_dt else None,
        end_date=end_dt.isoformat() if end_dt else None,
    )


def get_ticket_trends(
    db: Session,
    date_range: Optional[str] = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[TicketTrendPoint]:
    start_dt, end_dt, window_label = resolve_date_window(date_range, start_date, end_date)
    tickets = _filter_tickets_by_date(db, start_dt, end_dt)

    now = datetime.now(timezone.utc)

    # Determine timeline boundaries
    if start_dt is None:
        # All time: find earliest ticket
        if tickets:
            earliest = min(ensure_utc(t.created_at) for t in tickets if t.created_at)
            timeline_start = earliest.date()
        else:
            timeline_start = (now - timedelta(days=30)).date()
    else:
        timeline_start = start_dt.date()

    timeline_end = (end_dt or now).date()
    day_count = (timeline_end - timeline_start).days + 1
    day_count = max(1, min(day_count, 180))  # bound to reasonable range

    # Pre-populate dates map
    dates_map: Dict[str, Dict[str, int]] = {}
    for d in range(day_count):
        day_str = (timeline_start + timedelta(days=d)).strftime("%Y-%m-%d")
        dates_map[day_str] = {"created": 0, "resolved": 0, "breached": 0}

    for t in tickets:
        if t.created_at:
            c_date = ensure_utc(t.created_at).strftime("%Y-%m-%d")
            if c_date in dates_map:
                dates_map[c_date]["created"] += 1

        if t.status in DONE_STATUSES:
            res_time = ensure_utc(t.resolved_at) or ensure_utc(t.updated_at)
            if res_time:
                r_date = res_time.strftime("%Y-%m-%d")
                if r_date in dates_map:
                    dates_map[r_date]["resolved"] += 1

        eval_res = evaluate_ticket_sla_status(t, t.sla_policy, as_of=now)
        if eval_res["response_breached"] or eval_res["resolution_breached"]:
            # Attribute breach to ticket creation date
            if t.created_at:
                b_date = ensure_utc(t.created_at).strftime("%Y-%m-%d")
                if b_date in dates_map:
                    dates_map[b_date]["breached"] += 1

    result = [
        TicketTrendPoint(
            date=day_str,
            created=data["created"],
            resolved=data["resolved"],
            breached=data["breached"],
        )
        for day_str, data in sorted(dates_map.items())
    ]
    return result


def get_category_distribution(
    db: Session,
    date_range: Optional[str] = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[CategoryDistributionItem]:
    start_dt, end_dt, _ = resolve_date_window(date_range, start_date, end_date)
    tickets = _filter_tickets_by_date(db, start_dt, end_dt)

    total = len(tickets)
    counts: Dict[str, int] = defaultdict(int)

    for t in tickets:
        cat = (t.category or "other").lower()
        counts[cat] += 1

    # Ensure standard categories are present
    standard_categories = ["hardware", "software", "network", "access_management", "email", "security", "other"]
    for cat in standard_categories:
        counts.setdefault(cat, 0)

    result: List[CategoryDistributionItem] = []
    for cat, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        pct = round((count / total) * 100.0, 1) if total > 0 else 0.0
        result.append(
            CategoryDistributionItem(
                category=cat,
                category_label=CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                count=count,
                percentage=pct,
            )
        )
    return result


def get_priority_distribution(
    db: Session,
    date_range: Optional[str] = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[PriorityDistributionItem]:
    start_dt, end_dt, _ = resolve_date_window(date_range, start_date, end_date)
    tickets = _filter_tickets_by_date(db, start_dt, end_dt)

    total = len(tickets)
    counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for t in tickets:
        p = (t.priority or "medium").lower()
        counts[p] = counts.get(p, 0) + 1

    priority_order = ["critical", "high", "medium", "low"]
    result: List[PriorityDistributionItem] = []
    for p in priority_order:
        c = counts.get(p, 0)
        pct = round((c / total) * 100.0, 1) if total > 0 else 0.0
        result.append(
            PriorityDistributionItem(
                priority=p,
                priority_label=PRIORITY_LABELS.get(p, p.title()),
                count=c,
                percentage=pct,
            )
        )
    return result


def get_status_distribution(
    db: Session,
    date_range: Optional[str] = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[StatusDistributionItem]:
    start_dt, end_dt, _ = resolve_date_window(date_range, start_date, end_date)
    tickets = _filter_tickets_by_date(db, start_dt, end_dt)

    total = len(tickets)
    counts: Dict[str, int] = {
        "open": 0,
        "assigned": 0,
        "in_progress": 0,
        "pending": 0,
        "resolved": 0,
        "closed": 0,
    }

    for t in tickets:
        s = (t.status or "open").lower()
        counts[s] = counts.get(s, 0) + 1

    result: List[StatusDistributionItem] = []
    for s in ["open", "assigned", "in_progress", "pending", "resolved", "closed"]:
        c = counts.get(s, 0)
        pct = round((c / total) * 100.0, 1) if total > 0 else 0.0
        result.append(
            StatusDistributionItem(
                status=s,
                status_label=STATUS_LABELS.get(s, s.title()),
                count=c,
                percentage=pct,
            )
        )
    return result


def get_workload(
    db: Session,
    date_range: Optional[str] = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[WorkloadItem]:
    start_dt, end_dt, _ = resolve_date_window(date_range, start_date, end_date)
    tickets = _filter_tickets_by_date(db, start_dt, end_dt)
    groups = db.query(AssignmentGroup).order_by(AssignmentGroup.name.asc()).all()

    now = datetime.now(timezone.utc)

    # Initialize groups
    group_map: Dict[Optional[int], Dict[str, Any]] = {}
    for g in groups:
        group_map[g.id] = {
            "group_id": g.id,
            "group_name": g.name,
            "total_tickets": 0,
            "open_tickets": 0,
            "breached_tickets": 0,
        }
    # Unassigned group
    group_map[None] = {
        "group_id": None,
        "group_name": "Unassigned",
        "total_tickets": 0,
        "open_tickets": 0,
        "breached_tickets": 0,
    }

    for t in tickets:
        gid = t.group_id
        if gid not in group_map:
            group_map[gid] = {
                "group_id": gid,
                "group_name": t.group.name if t.group else "Other",
                "total_tickets": 0,
                "open_tickets": 0,
                "breached_tickets": 0,
            }

        group_map[gid]["total_tickets"] += 1
        if (t.status or "open").lower() not in DONE_STATUSES:
            group_map[gid]["open_tickets"] += 1

        eval_res = evaluate_ticket_sla_status(t, t.sla_policy, as_of=now)
        if eval_res["response_breached"] or eval_res["resolution_breached"]:
            group_map[gid]["breached_tickets"] += 1

    # Return items sorted by total tickets desc
    items = [WorkloadItem(**val) for val in group_map.values() if val["total_tickets"] > 0 or val["group_id"] is not None]
    items.sort(key=lambda x: x.total_tickets, reverse=True)
    return items


def get_sla_overview(db: Session) -> SLAOverviewResponse:
    """Comprehensive SLA overview including policy metrics, overdue tickets, and recent breaches."""
    policies = db.query(SLAPolicy).order_by(SLAPolicy.id.asc()).all()
    tickets = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.sla_policy),
            joinedload(Ticket.group),
            joinedload(Ticket.requester),
        )
        .order_by(Ticket.created_at.desc())
        .all()
    )

    now = datetime.now(timezone.utc)

    total_evaluated = len(tickets)
    total_breached = 0
    total_overdue = 0
    response_breached_count = 0
    resolution_breached_count = 0

    overdue_items: List[SLAIncidentItem] = []
    breached_items: List[SLAIncidentItem] = []

    # Map policy metrics
    policy_stats: Dict[int, Dict[str, Any]] = {}
    for p in policies:
        policy_stats[p.id] = {
            "active_tickets": 0,
            "resolved_tickets": 0,
            "breached_tickets": 0,
        }

    for t in tickets:
        eval_res = evaluate_ticket_sla_status(t, t.sla_policy, as_of=now)
        is_breached = eval_res["response_breached"] or eval_res["resolution_breached"]
        if is_breached:
            total_breached += 1
        if eval_res["response_breached"]:
            response_breached_count += 1
        if eval_res["resolution_breached"]:
            resolution_breached_count += 1
        if eval_res["is_overdue"]:
            total_overdue += 1

        # Track per-policy stats
        pid = t.sla_policy_id
        if pid in policy_stats:
            if (t.status or "open").lower() in DONE_STATUSES:
                policy_stats[pid]["resolved_tickets"] += 1
            else:
                policy_stats[pid]["active_tickets"] += 1
            if is_breached:
                policy_stats[pid]["breached_tickets"] += 1

        incident_item = SLAIncidentItem(
            id=t.id,
            ticket_number=t.ticket_number or f"INC{t.id:07d}",
            title=t.title,
            priority=t.priority,
            priority_label=PRIORITY_LABELS.get(t.priority, t.priority),
            status=t.status,
            assigned_group=t.group.name if t.group else None,
            created_by=t.requester.name if t.requester else None,
            created_at=ensure_utc(t.created_at) or now,
            response_deadline=ensure_utc(t.response_deadline or eval_res["response_deadline"]),
            resolution_deadline=ensure_utc(t.sla_deadline or eval_res["resolution_deadline"]),
            first_responded_at=ensure_utc(t.first_responded_at),
            resolved_at=ensure_utc(t.resolved_at),
            response_breached=eval_res["response_breached"],
            resolution_breached=eval_res["resolution_breached"],
            is_overdue=eval_res["is_overdue"],
            is_near_breach=eval_res["is_near_breach"],
            sla_status=eval_res["sla_status"],
            ticket_age_display=eval_res["age_display"],
        )

        if eval_res["is_overdue"]:
            overdue_items.append(incident_item)
        if is_breached:
            breached_items.append(incident_item)

    # Sort overdue by resolution deadline ascending (most urgently overdue first)
    overdue_items.sort(key=lambda x: x.resolution_deadline or x.created_at)
    # Sort breached by created_at descending
    breached_items.sort(key=lambda x: x.created_at, reverse=True)

    # Overall compliance rates
    if total_evaluated > 0:
        overall_compliance = round(((total_evaluated - total_breached) / total_evaluated) * 100.0, 1)
        resp_compliance = round(((total_evaluated - response_breached_count) / total_evaluated) * 100.0, 1)
        res_compliance = round(((total_evaluated - resolution_breached_count) / total_evaluated) * 100.0, 1)
    else:
        overall_compliance = 100.0
        resp_compliance = 100.0
        res_compliance = 100.0

    # Assemble policy metrics
    policy_metrics_list: List[SLAPolicyMetrics] = []
    for p in policies:
        stats = policy_stats.get(p.id, {"active_tickets": 0, "resolved_tickets": 0, "breached_tickets": 0})
        total_policy_tickets = stats["active_tickets"] + stats["resolved_tickets"]
        if total_policy_tickets > 0:
            p_comp = round(((total_policy_tickets - stats["breached_tickets"]) / total_policy_tickets) * 100.0, 1)
        else:
            p_comp = 100.0

        policy_metrics_list.append(
            SLAPolicyMetrics(
                policy=SLAPolicyResponse.model_validate(p),
                active_tickets=stats["active_tickets"],
                resolved_tickets=stats["resolved_tickets"],
                breached_tickets=stats["breached_tickets"],
                compliance_rate=p_comp,
            )
        )

    return SLAOverviewResponse(
        total_evaluated=total_evaluated,
        total_breached=total_breached,
        total_overdue=total_overdue,
        overall_compliance_rate=overall_compliance,
        response_compliance_rate=resp_compliance,
        resolution_compliance_rate=res_compliance,
        policies=policy_metrics_list,
        overdue_incidents=overdue_items[:50],
        recent_breaches=breached_items[:50],
    )
