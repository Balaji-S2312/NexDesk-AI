"""
SLA calculation and evaluation service for NexDesk AI.
Implements calendar-time and business-hours deadline calculations,
ticket age tracking, breach detection, and compliance status evaluation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple


WORK_DAY_START_HOUR = 9   # 09:00
WORK_DAY_END_HOUR = 17    # 17:00
MINUTES_PER_WORK_DAY = (WORK_DAY_END_HOUR - WORK_DAY_START_HOUR) * 60  # 480 minutes (8 hours)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize any datetime to timezone-aware UTC datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_calendar_deadline(start_dt: datetime, minutes: int) -> datetime:
    """Calculate deadline using 24/7 continuous calendar time."""
    start_utc = ensure_utc(start_dt)
    return start_utc + timedelta(minutes=max(0, int(minutes)))


def calculate_business_deadline(
    start_dt: datetime,
    minutes: int,
    work_start_hour: int = WORK_DAY_START_HOUR,
    work_end_hour: int = WORK_DAY_END_HOUR,
) -> datetime:
    """
    Calculate deadline using standard business hours (Mon-Fri, work_start to work_end).
    Skips non-business hours and weekends (Saturday=5, Sunday=6).
    """
    start_utc = ensure_utc(start_dt)
    minutes_left = max(0, int(minutes))
    cur = start_utc

    # Fast forward cur to a valid business hour window if outside
    def advance_to_business_window(dt: datetime) -> datetime:
        # Move forward until dt is Mon-Fri and between work_start and work_end
        while True:
            weekday = dt.weekday()
            # If weekend, advance to next Monday work_start:00
            if weekday == 5:  # Saturday
                dt = (dt + timedelta(days=2)).replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                continue
            if weekday == 6:  # Sunday
                dt = (dt + timedelta(days=1)).replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                continue

            # Weekday checks
            if dt.hour < work_start_hour:
                dt = dt.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                return dt
            if dt.hour >= work_end_hour:
                # Advance to next day at work_start
                dt = (dt + timedelta(days=1)).replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                continue
            return dt

    cur = advance_to_business_window(cur)

    while minutes_left > 0:
        day_end = cur.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)
        minutes_remaining_today = int((day_end - cur).total_seconds() // 60)

        if minutes_left <= minutes_remaining_today:
            cur = cur + timedelta(minutes=minutes_left)
            minutes_left = 0
        else:
            minutes_left -= minutes_remaining_today
            # Advance to start of next day and adjust to business window
            cur = (cur + timedelta(days=1)).replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
            cur = advance_to_business_window(cur)

    return cur


def compute_deadlines(
    created_at: datetime,
    response_minutes: int,
    resolution_hours: int,
    business_hours_only: bool = False,
) -> Tuple[datetime, datetime]:
    """
    Compute (response_deadline, resolution_deadline) from ticket creation time.
    """
    created_utc = ensure_utc(created_at)
    resolution_minutes = resolution_hours * 60

    if business_hours_only:
        resp_dl = calculate_business_deadline(created_utc, response_minutes)
        res_dl = calculate_business_deadline(created_utc, resolution_minutes)
    else:
        resp_dl = calculate_calendar_deadline(created_utc, response_minutes)
        res_dl = calculate_calendar_deadline(created_utc, resolution_minutes)

    return resp_dl, res_dl


def format_duration(seconds: int) -> str:
    """Format total seconds into human-readable duration ('2d 4h', '3h 15m', or '45m')."""
    if seconds < 0:
        seconds = 0
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def calculate_ticket_age(
    created_at: datetime,
    resolved_at: Optional[datetime] = None,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calculate age of ticket in seconds, decimal hours, and formatted display string."""
    start_dt = ensure_utc(created_at)
    end_dt = ensure_utc(resolved_at) if resolved_at else ensure_utc(as_of or datetime.now(timezone.utc))

    diff_seconds = max(0, int((end_dt - start_dt).total_seconds()))
    hours = round(diff_seconds / 3600.0, 2)
    display = format_duration(diff_seconds)

    return {
        "seconds": diff_seconds,
        "hours": hours,
        "display": display,
    }


def evaluate_ticket_sla_status(
    ticket: Any,
    policy: Any = None,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Evaluates response and resolution SLA compliance for a ticket.
    Returns breach flags, status, age, and remaining/elapsed time.
    """
    now_utc = ensure_utc(as_of or datetime.now(timezone.utc))
    created_at = ensure_utc(getattr(ticket, "created_at", None)) or now_utc
    resolved_at = ensure_utc(getattr(ticket, "resolved_at", None))
    first_responded_at = ensure_utc(getattr(ticket, "first_responded_at", None))
    response_deadline = ensure_utc(getattr(ticket, "response_deadline", None))
    resolution_deadline = ensure_utc(getattr(ticket, "sla_deadline", None))
    status = (getattr(ticket, "status", "") or "open").lower()

    # If deadlines were never set, compute fallback from policy or defaults
    if response_deadline is None or resolution_deadline is None:
        p_resp = getattr(policy, "response_time_minutes", 240) if policy else 240
        p_res = getattr(policy, "resolution_time_hours", 24) if policy else 24
        p_biz = getattr(policy, "business_hours_only", False) if policy else False
        calc_resp, calc_res = compute_deadlines(created_at, p_resp, p_res, p_biz)
        if response_deadline is None:
            response_deadline = calc_resp
        if resolution_deadline is None:
            resolution_deadline = calc_res

    # Age calculation
    age = calculate_ticket_age(created_at, resolved_at, now_utc)

    # 1. Response breach evaluation
    # If first response exists: did it occur after response_deadline?
    # If no response yet: has now passed response_deadline?
    response_breached = False
    if first_responded_at and response_deadline:
        response_breached = first_responded_at > response_deadline
    elif not first_responded_at and response_deadline:
        if status in ("assigned", "in_progress", "pending", "resolved", "closed"):
            # Responded without timestamp, treat as created_at or compliant unless created after deadline
            response_breached = False
        else:
            response_breached = now_utc > response_deadline

    # 2. Resolution breach evaluation
    # If resolved: was resolved_at after resolution_deadline?
    # If not resolved: has now passed resolution_deadline?
    resolution_breached = False
    is_resolved = status in ("resolved", "closed")
    if is_resolved:
        if resolved_at and resolution_deadline:
            resolution_breached = resolved_at > resolution_deadline
        elif resolution_deadline:
            # If resolved without explicit timestamp, check updated_at or assume compliant
            resolution_breached = False
    else:
        if resolution_deadline:
            resolution_breached = now_utc > resolution_deadline

    # Overdue indicator: unresolved tickets past resolution deadline
    is_overdue = (not is_resolved) and resolution_breached

    # Near breach indicator: active ticket, not breached yet, but within 20% of duration or <= 1 hour left
    is_near_breach = False
    time_remaining_seconds: Optional[int] = None
    if (not is_resolved) and (not resolution_breached) and resolution_deadline:
        time_remaining_seconds = max(0, int((resolution_deadline - now_utc).total_seconds()))
        total_duration_seconds = max(1, int((resolution_deadline - created_at).total_seconds()))
        # Near breach if <= 20% time left or <= 3600 seconds (1 hour)
        if (time_remaining_seconds <= total_duration_seconds * 0.20) or (time_remaining_seconds <= 3600):
            is_near_breach = True

    # Consolidated status category
    if response_breached and resolution_breached:
        sla_status = "both_breached"
    elif resolution_breached:
        sla_status = "resolution_breached"
    elif response_breached:
        sla_status = "response_breached"
    elif is_near_breach:
        sla_status = "near_breach"
    else:
        sla_status = "compliant"

    return {
        "sla_status": sla_status,
        "is_compliant": (not response_breached) and (not resolution_breached),
        "response_breached": response_breached,
        "resolution_breached": resolution_breached,
        "is_overdue": is_overdue,
        "is_near_breach": is_near_breach,
        "age_seconds": age["seconds"],
        "age_hours": age["hours"],
        "age_display": age["display"],
        "response_deadline": response_deadline,
        "resolution_deadline": resolution_deadline,
        "first_responded_at": first_responded_at,
        "time_remaining_seconds": time_remaining_seconds,
    }
