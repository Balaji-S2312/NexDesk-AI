"""Centralized in-app notification & event orchestration service (Module 9A)."""
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.user import User
from app.services.notifications.email_service import (
    CATEGORY_LABELS,
    STATUS_LABELS,
    send_ticket_assignment_email,
    send_ticket_priority_email,
    send_ticket_resolution_email,
    send_ticket_status_email,
    send_ticket_submission_email,
)
from app.services.tickets.rules import PRIORITY_LABELS

logger = logging.getLogger(__name__)


class NotificationNotFoundError(Exception):
    """Raised when a notification does not exist."""


class NotificationAccessError(Exception):
    """Raised when a user tries to modify/read another user's notification."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def serialize_notification(n: Notification) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    if n.metadata_json:
        try:
            meta = json.loads(n.metadata_json)
        except Exception:
            meta = {}
    return {
        "id": n.id,
        "recipient_user_id": n.recipient_user_id,
        "ticket_id": n.ticket_id,
        "ticket_number": n.ticket_number,
        "notification_type": n.notification_type,
        "title": n.title,
        "message": n.message,
        "link": n.link,
        "metadata": meta,
        "is_read": bool(n.is_read),
        "created_at": _as_utc(n.created_at),
        "read_at": _as_utc(n.read_at),
    }


def create_notification(
    db: Session,
    *,
    recipient_user_id: int,
    notification_type: str,
    title: str,
    message: str,
    event_key: str,
    ticket_id: Optional[int] = None,
    ticket_number: Optional[str] = None,
    link: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Notification:
    """Idempotently persist an in-app notification for a single recipient."""
    existing = db.query(Notification).filter(Notification.event_key == event_key).first()
    if existing:
        return existing

    row = Notification(
        recipient_user_id=recipient_user_id,
        ticket_id=ticket_id,
        ticket_number=ticket_number,
        notification_type=notification_type,
        event_key=event_key,
        title=title[:255],
        message=message,
        link=link,
        metadata_json=json.dumps(metadata or {}),
        is_read=False,
        created_at=_utc_now(),
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        found = db.query(Notification).filter(Notification.event_key == event_key).first()
        if found:
            return found
        raise


def notify_ticket_submitted(
    db: Session,
    ticket: Ticket,
    requester: User,
    send_emails: bool = True,
) -> List[Notification]:
    """EVENT A: Employee submission confirmation + Admin new incident alert."""
    created: List[Notification] = []
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    priority_label = PRIORITY_LABELS.get(ticket.priority, ticket.priority)
    cat_label = CATEGORY_LABELS.get(ticket.category, ticket.category.title())
    created_at_utc = _as_utc(ticket.created_at) or _utc_now()
    submitted_str = created_at_utc.strftime("%Y-%m-%d %H:%M UTC")
    link = f"/tickets/{ticket.id}"

    emp_notif = create_notification(
        db,
        recipient_user_id=requester.id,
        notification_type="ticket_submitted",
        title=f"Ticket Submitted: {ticket_num}",
        message=(
            f"Your ticket '{ticket.title}' ({ticket_num}) was submitted at {submitted_str}. "
            f"Current status: {status_label}."
        ),
        event_key=f"notif:ticket_submitted:{ticket.id}:user:{requester.id}",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        link=link,
        metadata={
            "ticket_number": ticket_num,
            "status": ticket.status,
            "priority": ticket.priority,
            "submitted_at": created_at_utc.isoformat(),
        },
    )
    created.append(emp_notif)

    admins = db.query(User).filter(User.role == "admin").all()
    for admin in admins:
        if admin.id == requester.id:
            continue
        adm_notif = create_notification(
            db,
            recipient_user_id=admin.id,
            notification_type="new_incident_alert",
            title=f"New Incident Alert: {ticket_num} [{priority_label}]",
            message=(
                f"{requester.name} submitted a new {cat_label} incident ({ticket_num}) "
                f"with {priority_label} priority."
            ),
            event_key=f"notif:new_incident:{ticket.id}:admin:{admin.id}",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            link=link,
            metadata={
                "ticket_number": ticket_num,
                "employee_name": requester.name,
                "category": cat_label,
                "priority": priority_label,
            },
        )
        created.append(adm_notif)

    if send_emails:
        try:
            send_ticket_submission_email(db, ticket, requester)
        except Exception as exc:
            logger.warning("Submission email failed gracefully for %s: %s", ticket_num, exc)

    return created


def notify_ticket_assigned(
    db: Session,
    ticket: Ticket,
    assigned_group_name: str,
    actor: Optional[User] = None,
    event_token: Optional[str] = None,
    send_emails: bool = True,
) -> List[Notification]:
    """EVENT B: Ticket assigned to a support group."""
    created: List[Notification] = []
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    token = event_token or f"{ticket.id}:assign:{assigned_group_name}"
    link = f"/tickets/{ticket.id}"

    emp_notif = create_notification(
        db,
        recipient_user_id=ticket.requester_id,
        notification_type="ticket_assigned",
        title=f"Ticket Assigned: {ticket_num}",
        message=(
            f"Ticket {ticket_num} has been assigned to {assigned_group_name}. "
            f"Current status: {status_label}."
        ),
        event_key=f"notif:ticket_assigned:{token}:user:{ticket.requester_id}",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        link=link,
        metadata={
            "ticket_number": ticket_num,
            "assigned_group": assigned_group_name,
            "status": ticket.status,
        },
    )
    created.append(emp_notif)

    admins = db.query(User).filter(User.role == "admin").all()
    for admin in admins:
        adm_notif = create_notification(
            db,
            recipient_user_id=admin.id,
            notification_type="ticket_assigned",
            title=f"Incident Routed: {ticket_num} -> {assigned_group_name}",
            message=(
                f"Incident {ticket_num} assigned to {assigned_group_name}"
                f"{f' by {actor.name}' if actor else ''}."
            ),
            event_key=f"notif:ticket_assigned:{token}:admin:{admin.id}",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            link=link,
            metadata={
                "ticket_number": ticket_num,
                "assigned_group": assigned_group_name,
                "status": ticket.status,
            },
        )
        created.append(adm_notif)

    if send_emails:
        try:
            send_ticket_assignment_email(db, ticket, assigned_group_name, token)
        except Exception as exc:
            logger.warning("Assignment email failed gracefully for %s: %s", ticket_num, exc)

    return created


def notify_ticket_priority_changed(
    db: Session,
    ticket: Ticket,
    old_priority: str,
    new_priority: str,
    actor: Optional[User] = None,
    event_token: Optional[str] = None,
    send_emails: bool = True,
) -> List[Notification]:
    """EVENT: Ticket priority updated by staff or system."""
    created: List[Notification] = []
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    old_p_label = PRIORITY_LABELS.get(old_priority, old_priority.title())
    new_p_label = PRIORITY_LABELS.get(new_priority, new_priority.title())
    actor_name = actor.name if actor else "Administrator"
    token = event_token or f"{ticket.id}:priority:{new_priority}"
    link = f"/tickets/{ticket.id}"

    emp_notif = create_notification(
        db,
        recipient_user_id=ticket.requester_id,
        notification_type="ticket_priority_updated",
        title=f"Ticket Priority Updated: {ticket_num}",
        message=(
            f"Ticket {ticket_num} priority changed from {old_p_label} to {new_p_label} "
            f"by {actor_name}."
        ),
        event_key=f"notif:ticket_priority:{token}:user:{ticket.requester_id}",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        link=link,
        metadata={
            "ticket_number": ticket_num,
            "old_priority": old_priority,
            "new_priority": new_priority,
            "actor": actor_name,
        },
    )
    created.append(emp_notif)

    if send_emails:
        try:
            send_ticket_priority_email(db, ticket, old_priority, new_priority, actor_name, token)
        except Exception as exc:
            logger.warning("Priority email failed gracefully for %s: %s", ticket_num, exc)

    return created


def notify_ticket_status_changed(
    db: Session,
    ticket: Ticket,
    old_status: str,
    new_status: str,
    actor: Optional[User] = None,
    event_token: Optional[str] = None,
    send_emails: bool = True,
) -> List[Notification]:
    """EVENT C: Meaningful ticket status transition notification."""
    if new_status == "resolved":
        return notify_ticket_resolved(
            db,
            ticket,
            ticket.resolution_notes or "",
            actor=actor,
            event_token=event_token,
            send_emails=send_emails,
        )

    created: List[Notification] = []
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    old_label = STATUS_LABELS.get(old_status, old_status.replace("_", " ").title())
    new_label = STATUS_LABELS.get(new_status, new_status.replace("_", " ").title())
    token = event_token or f"{ticket.id}:status:{old_status}->{new_status}"
    link = f"/tickets/{ticket.id}"

    if not actor or actor.id != ticket.requester_id:
        emp_notif = create_notification(
            db,
            recipient_user_id=ticket.requester_id,
            notification_type="ticket_status_updated",
            title=f"Status Updated: {ticket_num} ({new_label})",
            message=f"Ticket {ticket_num} moved from {old_label} to {new_label}.",
            event_key=f"notif:ticket_status:{token}:user:{ticket.requester_id}",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            link=link,
            metadata={
                "ticket_number": ticket_num,
                "old_status": old_status,
                "new_status": new_status,
            },
        )
        created.append(emp_notif)
    elif new_status == "closed":
        admins = db.query(User).filter(User.role == "admin").all()
        for admin in admins:
            adm_notif = create_notification(
                db,
                recipient_user_id=admin.id,
                notification_type="ticket_closed",
                title=f"Ticket Closed by Requester: {ticket_num}",
                message=f"{actor.name} confirmed resolution and closed ticket {ticket_num}.",
                event_key=f"notif:ticket_closed:{token}:admin:{admin.id}",
                ticket_id=ticket.id,
                ticket_number=ticket_num,
                link=link,
                metadata={"ticket_number": ticket_num, "status": "closed"},
            )
            created.append(adm_notif)

    if send_emails:
        try:
            send_ticket_status_email(db, ticket, old_status, new_status, token)
        except Exception as exc:
            logger.warning("Status email failed gracefully for %s: %s", ticket_num, exc)

    return created


def notify_ticket_resolved(
    db: Session,
    ticket: Ticket,
    resolution_notes: str,
    actor: Optional[User] = None,
    event_token: Optional[str] = None,
    send_emails: bool = True,
) -> List[Notification]:
    """EVENT D: Ticket resolved with resolution notes and timestamp."""
    created: List[Notification] = []
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    resolved_utc = _as_utc(ticket.resolved_at) or _utc_now()
    resolved_str = resolved_utc.strftime("%Y-%m-%d %H:%M UTC")
    notes_preview = (resolution_notes or "").strip()
    token = event_token or f"{ticket.id}:resolved:{int(resolved_utc.timestamp())}"
    link = f"/tickets/{ticket.id}"

    emp_notif = create_notification(
        db,
        recipient_user_id=ticket.requester_id,
        notification_type="ticket_resolved",
        title=f"Ticket Resolved: {ticket_num}",
        message=(
            f"Ticket {ticket_num} was resolved at {resolved_str}. "
            f"Resolution notes: {notes_preview or 'Resolved by IT support.'}"
        ),
        event_key=f"notif:ticket_resolved:{token}:user:{ticket.requester_id}",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        link=link,
        metadata={
            "ticket_number": ticket_num,
            "resolution_notes": notes_preview,
            "resolved_at": resolved_utc.isoformat(),
            "status": ticket.status,
        },
    )
    created.append(emp_notif)

    admins = db.query(User).filter(User.role == "admin").all()
    for admin in admins:
        adm_notif = create_notification(
            db,
            recipient_user_id=admin.id,
            notification_type="ticket_resolved_confirmation",
            title=f"Resolution Confirmed: {ticket_num}",
            message=(
                f"Incident {ticket_num} marked as Resolved at {resolved_str}"
                f"{f' by {actor.name}' if actor else ''}."
            ),
            event_key=f"notif:ticket_resolved:{token}:admin:{admin.id}",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            link=link,
            metadata={
                "ticket_number": ticket_num,
                "resolved_at": resolved_utc.isoformat(),
                "status": ticket.status,
            },
        )
        created.append(adm_notif)

    if send_emails:
        try:
            send_ticket_resolution_email(db, ticket, notes_preview, token)
        except Exception as exc:
            logger.warning("Resolution email failed gracefully for %s: %s", ticket_num, exc)

    return created


def get_unread_count(db: Session, current_user: User) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .count()
    )


def get_user_notifications(
    db: Session,
    current_user: User,
    *,
    unread_only: bool = False,
    ticket_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    query = db.query(Notification).filter(Notification.recipient_user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    if ticket_id is not None:
        query = query.filter(Notification.ticket_id == ticket_id)

    total = query.count()
    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    unread_count = get_unread_count(db, current_user)
    return {
        "items": [serialize_notification(r) for r in rows],
        "total": total,
        "unread_count": unread_count,
    }


def mark_notification_read(db: Session, notification_id: int, current_user: User) -> Notification:
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise NotificationNotFoundError("Notification not found.")
    if notif.recipient_user_id != current_user.id:
        raise NotificationAccessError("You do not have permission to access this notification.")

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = _utc_now()
        db.commit()
        db.refresh(notif)
    return notif


def mark_all_notifications_read(db: Session, current_user: User) -> int:
    now = _utc_now()
    unread_rows = (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .all()
    )
    for row in unread_rows:
        row.is_read = True
        row.read_at = now
    if unread_rows:
        db.commit()
    return len(unread_rows)
