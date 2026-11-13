"""Ticket workflow: creation, updates, history and audit logging."""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.assignment_group import AssignmentGroup
from app.models.audit_log import AuditLog
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket, TicketHistory
from app.models.user import User
from app.services.tickets.rules import (
    DEFAULT_RESOLUTION_HOURS,
    DEFAULT_RESPONSE_MINUTES,
    DONE_STATUSES,
    PRIORITY_LABELS,
    calculate_priority,
    calculate_sla_deadline,
)
from app.services.sla.calculator import (
    compute_deadlines,
    evaluate_ticket_sla_status,
)


class TicketRuleError(ValueError):
    """Raised when a requested change violates a workflow rule (mapped to HTTP 422)."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; everything we store is UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _resolve_sla(db: Session, priority: str, created_at: datetime):
    policy = db.query(SLAPolicy).filter(SLAPolicy.priority == priority).first()
    resp_mins = policy.response_time_minutes if policy and getattr(policy, "response_time_minutes", None) else DEFAULT_RESPONSE_MINUTES.get(priority, 240)
    res_hrs = policy.resolution_time_hours if policy and getattr(policy, "resolution_time_hours", None) else DEFAULT_RESOLUTION_HOURS.get(priority, 24)
    biz_only = bool(getattr(policy, "business_hours_only", False)) if policy else False
    resp_dl, res_dl = compute_deadlines(as_utc(created_at), resp_mins, res_hrs, biz_only)
    return policy, resp_dl, res_dl


def _audit(db: Session, user: User, action: str, ticket: Ticket, details: str, ip: Optional[str]) -> None:
    db.add(AuditLog(
        user_id=user.id,
        action=action,
        resource_type="ticket",
        resource_id=str(ticket.id),
        details=details,
        ip_address=ip,
        created_at=utc_now(),
    ))


def _history(db: Session, ticket: Ticket, user: User, field: str, old: Any, new: Any, when: datetime) -> None:
    db.add(TicketHistory(
        ticket_id=ticket.id,
        user_id=user.id,
        field_changed=field,
        old_value=None if old is None else str(old),
        new_value=None if new is None else str(new),
        created_at=when,
    ))


def create_ticket(
    db: Session,
    requester: User,
    data: Dict[str, Any],
    ip: Optional[str] = None,
    created_at: Optional[datetime] = None,
    notify: bool = True,
    background_tasks: Any = None,
) -> Ticket:
    """Validate-already-done data -> priority, status, SLA, ticket number, history + audit."""
    now = created_at or utc_now()
    priority = calculate_priority(data["impact"], data["urgency"])
    policy, resp_deadline, res_deadline = _resolve_sla(db, priority, now)

    ticket = Ticket(
        title=data["title"],
        description=data["description"],
        category=data["category"],
        subcategory=data.get("subcategory"),
        impact=data["impact"],
        urgency=data["urgency"],
        priority=priority,
        status="open",
        requester_id=requester.id,
        sla_policy_id=policy.id if policy else None,
        response_deadline=resp_deadline,
        sla_deadline=res_deadline,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(ticket)
        db.flush()  # obtain primary key
        ticket.ticket_number = f"INC{ticket.id:07d}"
        _history(db, ticket, requester, "created", None,
                 f"{ticket.ticket_number} created with priority {PRIORITY_LABELS[priority]}", now)
        _audit(db, requester, "CREATE_TICKET", ticket,
               f"Created {ticket.ticket_number}: {ticket.title} [{PRIORITY_LABELS[priority]}]", ip)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(ticket)

    if notify:
        try:
            from app.services.notifications.notification_service import notify_ticket_submitted

            notify_ticket_submitted(db, ticket, requester, background_tasks=background_tasks)
        except Exception as exc:
            logger.warning("Post-create notification failed for %s: %s", ticket.ticket_number, exc)

    return ticket


TRACKED_FIELDS = ("title", "description", "category", "subcategory", "impact",
                  "urgency", "status", "resolution_notes")


def update_ticket(
    db: Session,
    ticket: Ticket,
    actor: User,
    changes: Dict[str, Any],
    ip: Optional[str] = None,
    when: Optional[datetime] = None,
    notify: bool = True,
    background_tasks: Any = None,
) -> List[Dict[str, Any]]:
    """Apply changes, recording old/new value, actor and timestamps. Returns the change list."""
    now = when or utc_now()
    recorded: List[Dict[str, Any]] = []

    def record(field: str, old: Any, new: Any) -> None:
        recorded.append({"field": field, "old": old, "new": new})

    changes = dict(changes)

    # Auto-move to "assigned" when a group is set on an untouched open ticket.
    if changes.get("group_id") and "status" not in changes and ticket.status == "open":
        changes["status"] = "assigned"

    # Resolve group first (validates existence).
    group_name_old = ticket.group.name if ticket.group else None
    new_group: Optional[AssignmentGroup] = None
    group_changed = False
    if "group_id" in changes:
        gid = changes["group_id"]
        if gid is not None:
            new_group = db.query(AssignmentGroup).filter(AssignmentGroup.id == gid).first()
            if not new_group:
                raise TicketRuleError(f"Assignment group {gid} does not exist")
        group_changed = gid != ticket.group_id

    # Resolution rules
    new_status = changes.get("status", ticket.status)
    if new_status in DONE_STATUSES:
        notes = changes.get("resolution_notes", ticket.resolution_notes)
        if not notes or not str(notes).strip():
            raise TicketRuleError("Resolution notes are required to resolve or close a ticket")

    try:
        for field in TRACKED_FIELDS:
            if field in changes and changes[field] != getattr(ticket, field):
                old = getattr(ticket, field)
                setattr(ticket, field, changes[field])
                record(field, old, changes[field])

        if group_changed:
            ticket.group_id = new_group.id if new_group else None
            record("assigned_group", group_name_old, new_group.name if new_group else None)

        # first_responded_at bookkeeping: record first response when moving away from "open" or setting assigned group
        if ticket.first_responded_at is None:
            if ticket.status != "open" or ticket.group_id is not None:
                ticket.first_responded_at = now
                record("first_responded_at", None, as_utc(now).isoformat())

        # resolved_at bookkeeping
        if "status" in changes:
            if ticket.status in DONE_STATUSES and ticket.resolved_at is None:
                ticket.resolved_at = now
            elif ticket.status not in DONE_STATUSES and ticket.resolved_at is not None:
                ticket.resolved_at = None

        # Impact/urgency drive priority and SLA deadline.
        if any(r["field"] in ("impact", "urgency") for r in recorded):
            old_priority, old_deadline = ticket.priority, ticket.sla_deadline
            ticket.priority = calculate_priority(ticket.impact, ticket.urgency)
            if ticket.priority != old_priority:
                policy, resp_deadline, res_deadline = _resolve_sla(db, ticket.priority, ticket.created_at)
                ticket.sla_policy_id = policy.id if policy else None
                ticket.response_deadline = resp_deadline
                ticket.sla_deadline = res_deadline
                record("priority", PRIORITY_LABELS[old_priority], PRIORITY_LABELS[ticket.priority])
                record("sla_deadline",
                       as_utc(old_deadline).isoformat() if old_deadline else None,
                       as_utc(res_deadline).isoformat())

        if recorded:
            ticket.updated_at = now
            for r in recorded:
                _history(db, ticket, actor, r["field"], r["old"], r["new"], now)
            summary = "; ".join(f"{r['field']}: {r['old']} -> {r['new']}" for r in recorded)
            _audit(db, actor, "UPDATE_TICKET", ticket, f"{ticket.ticket_number}: {summary}", ip)
            db.commit()
            db.refresh(ticket)
    except Exception:
        db.rollback()
        raise

    if recorded and notify:
        try:
            from app.services.notifications.notification_service import (
                notify_ticket_assigned,
                notify_ticket_resolved,
                notify_ticket_status_changed,
            )

            group_change = next((r for r in recorded if r["field"] == "assigned_group" and r["new"]), None)
            status_change = next((r for r in recorded if r["field"] == "status"), None)
            priority_change = next((r for r in recorded if r["field"] == "priority"), None)

            if priority_change:
                from app.services.notifications.notification_service import notify_ticket_priority_changed

                notify_ticket_priority_changed(
                    db,
                    ticket,
                    str(priority_change["old"]),
                    str(priority_change["new"]),
                    actor=actor,
                    event_token=f"{ticket.id}:priority:{priority_change['old']}->{priority_change['new']}:{now.isoformat()}",
                    background_tasks=background_tasks,
                )

            if group_change:
                notify_ticket_assigned(
                    db,
                    ticket,
                    str(group_change["new"]),
                    actor=actor,
                    event_token=f"{ticket.id}:assign:{group_change['new']}:{now.isoformat()}",
                    background_tasks=background_tasks,
                )

            if status_change:
                if status_change["new"] == "resolved":
                    notify_ticket_resolved(
                        db,
                        ticket,
                        ticket.resolution_notes or "",
                        actor=actor,
                        event_token=f"{ticket.id}:resolved:{now.isoformat()}",
                        background_tasks=background_tasks,
                    )
                elif not (group_change and status_change["new"] == "assigned"):
                    notify_ticket_status_changed(
                        db,
                        ticket,
                        str(status_change["old"] or "open"),
                        str(status_change["new"]),
                        actor=actor,
                        event_token=f"{ticket.id}:status:{status_change['old']}->{status_change['new']}:{now.isoformat()}",
                        background_tasks=background_tasks,
                    )
        except Exception as exc:
            logger.warning("Post-update notification failed for %s: %s", ticket.ticket_number, exc)

    return recorded


def serialize_ticket(t: Ticket) -> Dict[str, Any]:
    now = utc_now()
    eval_sla = evaluate_ticket_sla_status(t, getattr(t, "sla_policy", None), as_of=now)
    resp_dl = as_utc(t.response_deadline or eval_sla["response_deadline"])
    res_dl = as_utc(t.sla_deadline or eval_sla["resolution_deadline"])
    first_resp = as_utc(t.first_responded_at)
    resolved_at = as_utc(t.resolved_at)

    return {
        "id": t.id,
        "ticket_number": t.ticket_number or f"INC{t.id:07d}",
        "title": t.title,
        "description": t.description,
        "category": t.category,
        "subcategory": t.subcategory,
        "impact": t.impact,
        "urgency": t.urgency,
        "priority": t.priority,
        "priority_label": PRIORITY_LABELS.get(t.priority, t.priority),
        "status": t.status,
        "group_id": t.group_id,
        "assigned_group": t.group.name if t.group else None,
        "requester_id": t.requester_id,
        "created_by": t.requester.name if t.requester else None,
        "created_at": as_utc(t.created_at),
        "updated_at": as_utc(t.updated_at),
        "response_deadline": resp_dl,
        "sla_deadline": res_dl,
        "first_responded_at": first_resp,
        "sla_breached": eval_sla["resolution_breached"] or eval_sla["response_breached"],
        "response_breached": eval_sla["response_breached"],
        "resolution_breached": eval_sla["resolution_breached"],
        "is_overdue": eval_sla["is_overdue"],
        "is_near_breach": eval_sla["is_near_breach"],
        "sla_status": eval_sla["sla_status"],
        "ticket_age_hours": eval_sla["age_hours"],
        "ticket_age_display": eval_sla["age_display"],
        "resolution_notes": t.resolution_notes,
        "resolved_at": resolved_at,
    }
