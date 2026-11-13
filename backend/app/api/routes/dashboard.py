from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_admin
from app.database.session import get_db
from app.models.assignment_group import AssignmentGroup
from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.user import User
from app.services.notifications.notification_service import serialize_notification
from app.services.tickets.rules import DONE_STATUSES, OPEN_STATUSES, PRIORITY_LABELS
from app.services.tickets.service import as_utc, create_ticket, update_ticket

router = APIRouter(prefix="/dashboard", tags=["Dashboard Metrics"])

CATEGORY_LABELS = {
    "hardware": "Hardware",
    "software": "Software",
    "network": "Network",
    "access_management": "Access Mgmt",
    "email": "Email",
    "security": "Security",
    "other": "Other",
}


def _ticket_row(t: Ticket, admin_view: bool) -> Dict[str, Any]:
    row = {
        "id": t.id,
        "ticket_number": t.ticket_number,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "priority_label": PRIORITY_LABELS.get(t.priority, t.priority),
        "category": t.category,
        "assigned_group": t.group.name if t.group else None,
        "created_at": as_utc(t.created_at).isoformat() if t.created_at else None,
        "updated_at": as_utc(t.updated_at).isoformat() if t.updated_at else None,
        "resolved_at": as_utc(t.resolved_at).isoformat() if t.resolved_at else None,
        "resolution_notes": t.resolution_notes,
    }
    if admin_view:
        row["requester"] = t.requester.name if t.requester else "Unknown"
        row["assignee"] = t.assignee.name if t.assignee else "Unassigned"
    return row


def _is_breached(t: Ticket, now: datetime) -> bool:
    if t.sla_deadline is None:
        return False
    deadline = as_utc(t.sla_deadline)
    if t.resolved_at is not None:
        return as_utc(t.resolved_at) > deadline
    return now > deadline


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Live, role-scoped metrics computed from the tickets table (nothing is hardcoded)."""
    now = datetime.now(timezone.utc)

    if current_user.role == "admin":
        tickets: List[Ticket] = (
            db.query(Ticket).options(joinedload(Ticket.requester), joinedload(Ticket.assignee), joinedload(Ticket.group)).all()
        )
        total = len(tickets)
        resolved_durations = [
            (as_utc(t.resolved_at) - as_utc(t.created_at)).total_seconds() / 3600
            for t in tickets if t.resolved_at is not None
        ]
        avg_resolution = round(sum(resolved_durations) / len(resolved_durations), 1) if resolved_durations else 0.0

        priority_colors = {"critical": "#f43f5e", "high": "#f97316", "medium": "#3b82f6", "low": "#10b981"}
        priority_counts = {p: 0 for p in priority_colors}
        category_counts: Dict[str, int] = {}
        for t in tickets:
            priority_counts[t.priority] = priority_counts.get(t.priority, 0) + 1
            category_counts[t.category] = category_counts.get(t.category, 0) + 1

        today = now.date()
        trends = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            trends.append({
                "date": day.strftime("%b %d"),
                "incidents": sum(1 for t in tickets if as_utc(t.created_at).date() == day),
                "resolved": sum(1 for t in tickets if t.resolved_at and as_utc(t.resolved_at).date() == day),
            })

        recent = sorted(tickets, key=lambda t: as_utc(t.created_at), reverse=True)[:8]
        recently_assigned = [
            _ticket_row(t, True)
            for t in sorted(
                (t for t in tickets if t.group_id is not None),
                key=lambda x: as_utc(x.updated_at or x.created_at),
                reverse=True,
            )[:5]
        ]
        recently_resolved = [
            _ticket_row(t, True)
            for t in sorted(
                (t for t in tickets if t.status in DONE_STATUSES),
                key=lambda x: as_utc(x.resolved_at or x.updated_at or x.created_at),
                reverse=True,
            )[:5]
        ]
        recent_admin_notifs = (
            db.query(Notification)
            .filter(Notification.recipient_user_id == current_user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(6)
            .all()
        )
        return {
            "role": "admin",
            "is_development_baseline": total == 0,
            "metrics": {
                "total_incidents": total,
                "open_incidents": sum(1 for t in tickets if t.status in ("open", "assigned", "pending")),
                "in_progress_incidents": sum(1 for t in tickets if t.status == "in_progress"),
                "resolved_incidents": sum(1 for t in tickets if t.status in DONE_STATUSES),
                "sla_breaches": sum(1 for t in tickets if _is_breached(t, now)),
                "average_resolution_hours": avg_resolution,
            },
            "priority_distribution": [
                {"priority": PRIORITY_LABELS.get(p, p), "count": c, "color": priority_colors.get(p, "#64748b")}
                for p, c in priority_counts.items()
            ],
            "category_distribution": [
                {"category": CATEGORY_LABELS.get(c, c.title()), "count": n} for c, n in sorted(category_counts.items())
            ],
            "incident_trends": trends,
            "recent_incidents": [_ticket_row(t, True) for t in recent],
            "recently_assigned_incidents": recently_assigned,
            "recently_resolved_incidents": recently_resolved,
            "recent_notifications": [
                {
                    **serialize_notification(n),
                    "created_at": as_utc(n.created_at).isoformat() if n.created_at else None,
                    "read_at": as_utc(n.read_at).isoformat() if n.read_at else None,
                }
                for n in recent_admin_notifs
            ],
        }

    base = db.query(Ticket).filter(Ticket.requester_id == current_user.id)
    recent = (
        base.options(joinedload(Ticket.group)).order_by(Ticket.created_at.desc()).limit(5).all()
    )
    logs = (
        db.query(AuditLog).filter(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc()).limit(5).all()
    )
    total = base.count()
    return {
        "role": "employee",
        "is_development_baseline": total == 0,
        "metrics": {
            "total_tickets": total,
            "open_tickets": base.filter(Ticket.status.in_(OPEN_STATUSES)).count(),
            "resolved_tickets": base.filter(Ticket.status.in_(DONE_STATUSES)).count(),
        },
        "recent_tickets": [_ticket_row(t, False) for t in recent],
        "recent_activity": [
            {
                "id": log.id,
                "action": log.action,
                "resource_type": log.resource_type,
                "details": log.details,
                "created_at": as_utc(log.created_at).isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# (title, description, category, subcategory, impact, urgency, hours_ago, status, group, resolution_notes)
_DEMO = [
    ("VPN gateway connection timed out (Error 504)", "Employees in the London office cannot connect to the OpenVPN gateway.", "network", "VPN", "high", "high", 2, "in_progress", "Network Operations", None),
    ("MacBook Pro screen flickering and kernel panic", "Display shuts off intermittently when docked to a Thunderbolt 4 monitor.", "hardware", "Laptop", "medium", "high", 6, "assigned", "Tier 1 Service Desk", None),
    ("Google SSO login failing on staging", "Callback URL mismatch on the OAuth2 redirect URI in staging.", "software", "SSO", "medium", "medium", 30, "resolved", "Cloud & Infrastructure", "Updated redirect URI in the identity provider and redeployed."),
    ("Request GitHub organization write access", "Need write permission to backend and frontend repositories for sprint work.", "access_management", "Repository access", "low", "low", 52, "closed", "Cybersecurity", "Access granted after manager approval."),
    ("Phishing email reported by finance team", "Multiple users received a spoofed invoice email with a malicious link.", "security", "Phishing", "high", "medium", 1, "open", None, None),
    ("Outlook calendar not syncing on mobile", "Meeting invites stopped appearing on iOS after password rotation.", "email", "Calendar", "low", "medium", 20, "pending", "Tier 1 Service Desk", None),
    ("Boardroom A conference microphone not detected", "Ceiling microphone array disconnected after firmware update.", "hardware", "Peripherals", "medium", "low", 4, "in_progress", "Tier 1 Service Desk", None),
]


@router.post("/seed-demo-tickets")
def seed_demo_tickets(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin-only: loads sample incidents (through the real ticket workflow) when the queue is nearly empty."""
    existing = db.query(Ticket).count()
    if existing >= 5:
        return {"message": "Tickets already exist in database.", "count": existing}

    emp = db.query(User).filter(User.role == "employee").first() or admin
    groups = {g.name: g for g in db.query(AssignmentGroup).all()}
    now = datetime.now(timezone.utc)
    created = 0
    for title, desc, cat, sub, imp, urg, hours_ago, status_, group, notes in _DEMO:
        created_at = now - timedelta(hours=hours_ago)
        ticket = create_ticket(
            db, emp,
            {"title": title, "description": desc, "category": cat, "subcategory": sub, "impact": imp, "urgency": urg},
            created_at=created_at,
            notify=False,
        )
        changes: Dict[str, Any] = {}
        if group and group in groups:
            changes["group_id"] = groups[group].id
        if status_ != "open":
            changes["status"] = status_
        if notes:
            changes["resolution_notes"] = notes
        if changes:
            when = created_at + timedelta(hours=min(hours_ago, 3) if status_ in DONE_STATUSES else min(hours_ago, 1))
            update_ticket(db, ticket, admin, changes, when=when, notify=False)
        created += 1
    return {"message": "Demo tickets seeded successfully.", "count": created}
