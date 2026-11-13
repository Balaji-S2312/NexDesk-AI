"""SMTP email delivery service with retries, idempotency, and sanitized audit logging."""
from datetime import datetime, timezone
from email.message import EmailMessage
import logging
import re
import smtplib
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import EmailDeliveryLog
from app.models.ticket import Ticket
from app.models.user import User
from app.services.notifications.notification_templates import (
    render_ticket_assignment_email,
    render_ticket_resolution_email,
    render_ticket_status_email,
    render_ticket_submission_email,
)
from app.services.tickets.rules import PRIORITY_LABELS

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

STATUS_LABELS = {
    "open": "Open",
    "assigned": "Assigned",
    "in_progress": "In Progress",
    "pending": "Pending",
    "resolved": "Resolved",
    "closed": "Closed",
}

CATEGORY_LABELS = {
    "hardware": "Hardware",
    "software": "Software",
    "network": "Network",
    "access_management": "Access Management",
    "email": "Email",
    "security": "Security",
    "other": "Other",
}

MEANINGFUL_STATUS_EMAILS = {"open", "assigned", "in_progress", "pending", "closed"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_valid_email(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    cleaned = value.strip()
    if "\r" in cleaned or "\n" in cleaned or len(cleaned) > 254:
        return False
    return bool(_EMAIL_RE.match(cleaned))


def is_smtp_configured() -> bool:
    return bool(
        settings.SMTP_HOST
        and settings.SMTP_HOST.strip()
        and settings.SMTP_FROM_EMAIL
        and is_valid_email(settings.SMTP_FROM_EMAIL.strip())
        and settings.SMTP_PASSWORD
        and settings.SMTP_PASSWORD.strip()
    )


def get_admin_notification_email() -> str:
    configured = (settings.ADMIN_NOTIFICATION_EMAIL or "").strip()
    return configured if is_valid_email(configured) else "balaji.poet2312s@gmail.com"


def _sanitize_smtp_error(err: Exception) -> str:
    msg = str(err) or type(err).__name__
    for secret in (settings.SMTP_PASSWORD, settings.SMTP_USERNAME):
        if secret:
            msg = msg.replace(secret, "[REDACTED]")
    return msg[:500]


def _deliver_smtp_message(msg: EmailMessage) -> None:
    """Open SMTP connection using environment configuration and send EmailMessage."""
    with smtplib.SMTP(
        settings.SMTP_HOST.strip(),
        int(settings.SMTP_PORT),
        timeout=int(settings.SMTP_TIMEOUT_SECONDS),
    ) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)


def _ticket_url(ticket: Ticket) -> str:
    base = (settings.FRONTEND_BASE_URL or "http://localhost:5173").rstrip("/")
    return f"{base}/tickets/{ticket.id}"


def send_email(
    db: Session,
    *,
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    event_type: str,
    event_key: str,
    ticket_id: Optional[int] = None,
    ticket_number: Optional[str] = None,
    recipient_user_id: Optional[int] = None,
    recipient_verified: bool = False,
) -> EmailDeliveryLog:
    """
    Safely deliver an HTML email with idempotency, retry handling, and DB audit logging.
    Never raises on SMTP errors or missing configuration, and never rolls back caller commits.
    """
    clean_recipient = (recipient_email or "").strip()
    existing = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.event_key == event_key).first()
    if existing and existing.delivery_status in ("sent", "skipped_unconfigured"):
        return existing

    if not is_valid_email(clean_recipient):
        log_row = existing or EmailDeliveryLog(
            recipient_user_id=recipient_user_id,
            recipient_email=clean_recipient[:255] or "invalid",
            recipient_verified=bool(recipient_verified),
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            event_type=event_type,
            event_key=event_key,
            subject=subject[:255],
            delivery_status="failed",
            attempt_count=0,
            error_message="Invalid recipient email address.",
            created_at=_utc_now(),
        )
        if existing:
            log_row.delivery_status = "failed"
            log_row.error_message = "Invalid recipient email address."
        else:
            db.add(log_row)
        db.commit()
        db.refresh(log_row)
        return log_row

    if not is_smtp_configured():
        log_row = existing or EmailDeliveryLog(
            recipient_user_id=recipient_user_id,
            recipient_email=clean_recipient,
            recipient_verified=bool(recipient_verified),
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            event_type=event_type,
            event_key=event_key,
            subject=subject[:255],
            delivery_status="skipped_unconfigured",
            attempt_count=0,
            error_message="SMTP server is not configured; in-app notification created.",
            created_at=_utc_now(),
        )
        if not existing:
            db.add(log_row)
        db.commit()
        db.refresh(log_row)
        return log_row

    msg = EmailMessage()
    from_name = (settings.SMTP_FROM_NAME or "NexDesk AI").strip()
    from_email = settings.SMTP_FROM_EMAIL.strip()
    msg["Subject"] = subject.replace("\r", "").replace("\n", "")
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = clean_recipient
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    max_attempts = max(1, int(settings.SMTP_MAX_RETRIES))
    attempts = 0
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None

    for _ in range(max_attempts):
        attempts += 1
        try:
            _deliver_smtp_message(msg)
            sent_at = _utc_now()
            last_error = None
            break
        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            last_error = _sanitize_smtp_error(exc)
            logger.warning(
                "Email delivery attempt %s/%s failed for event=%s ticket=%s: %s",
                attempts,
                max_attempts,
                event_type,
                ticket_number,
                last_error,
            )

    status_val = "sent" if sent_at is not None else "failed"
    try:
        if existing:
            existing.delivery_status = status_val
            existing.attempt_count = existing.attempt_count + attempts
            existing.error_message = last_error
            existing.sent_at = sent_at
            log_row = existing
        else:
            log_row = EmailDeliveryLog(
                recipient_user_id=recipient_user_id,
                recipient_email=clean_recipient,
                recipient_verified=bool(recipient_verified),
                ticket_id=ticket_id,
                ticket_number=ticket_number,
                event_type=event_type,
                event_key=event_key,
                subject=subject[:255],
                delivery_status=status_val,
                attempt_count=attempts,
                error_message=last_error,
                created_at=_utc_now(),
                sent_at=sent_at,
            )
            db.add(log_row)
        db.commit()
        db.refresh(log_row)
        return log_row
    except Exception as db_exc:
        db.rollback()
        logger.error("Failed persisting EmailDeliveryLog: %s", db_exc)
        return existing or EmailDeliveryLog(
            recipient_email=clean_recipient,
            event_type=event_type,
            event_key=event_key,
            subject=subject[:255],
            delivery_status="failed",
            attempt_count=attempts,
            error_message=last_error or "Database log persistence failure",
        )


def send_ticket_submission_email(db: Session, ticket: Ticket, requester: User) -> None:
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    priority_label = PRIORITY_LABELS.get(ticket.priority, ticket.priority)
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    category_label = CATEGORY_LABELS.get(ticket.category, ticket.category.title())
    created_str = ticket.created_at.strftime("%Y-%m-%d %H:%M UTC") if ticket.created_at else "Just now"
    url = _ticket_url(ticket)

    emp_tpl = render_ticket_submission_email(
        ticket_number=ticket_num,
        title=ticket.title,
        status_label=status_label,
        priority_label=priority_label,
        category_label=category_label,
        created_at_str=created_str,
        ticket_url=url,
        recipient_name=requester.name,
        is_admin=False,
        is_verified=bool(getattr(requester, "email_verified", False)),
    )
    send_email(
        db,
        recipient_email=requester.email,
        subject=emp_tpl["subject"],
        html_body=emp_tpl["html"],
        text_body=emp_tpl["text"],
        event_type="ticket_submitted",
        event_key=f"email:ticket_submitted:{ticket.id}:employee:{requester.id}",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=requester.id,
        recipient_verified=bool(getattr(requester, "email_verified", False)),
    )

    admin_email = get_admin_notification_email()
    admin_tpl = render_ticket_submission_email(
        ticket_number=ticket_num,
        title=ticket.title,
        status_label=status_label,
        priority_label=priority_label,
        category_label=category_label,
        created_at_str=created_str,
        ticket_url=url,
        recipient_name="NexDesk Administrator",
        is_admin=True,
        requester_name=requester.name,
        is_verified=True,
    )
    send_email(
        db,
        recipient_email=admin_email,
        subject=admin_tpl["subject"],
        html_body=admin_tpl["html"],
        text_body=admin_tpl["text"],
        event_type="new_incident_alert",
        event_key=f"email:new_incident:{ticket.id}:admin",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=None,
        recipient_verified=True,
    )


def send_ticket_assignment_email(
    db: Session,
    ticket: Ticket,
    assigned_group: str,
    event_suffix: str,
) -> None:
    requester = ticket.requester or db.query(User).filter(User.id == ticket.requester_id).first()
    if not requester:
        return
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    priority_label = PRIORITY_LABELS.get(ticket.priority, ticket.priority)
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    url = _ticket_url(ticket)

    emp_tpl = render_ticket_assignment_email(
        ticket_number=ticket_num,
        title=ticket.title,
        assigned_group=assigned_group,
        status_label=status_label,
        priority_label=priority_label,
        ticket_url=url,
        recipient_name=requester.name,
        is_admin=False,
        is_verified=bool(getattr(requester, "email_verified", False)),
    )
    send_email(
        db,
        recipient_email=requester.email,
        subject=emp_tpl["subject"],
        html_body=emp_tpl["html"],
        text_body=emp_tpl["text"],
        event_type="ticket_assigned",
        event_key=f"email:ticket_assigned:{event_suffix}:employee",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=requester.id,
        recipient_verified=bool(getattr(requester, "email_verified", False)),
    )

    admin_email = get_admin_notification_email()
    admin_tpl = render_ticket_assignment_email(
        ticket_number=ticket_num,
        title=ticket.title,
        assigned_group=assigned_group,
        status_label=status_label,
        priority_label=priority_label,
        ticket_url=url,
        recipient_name="NexDesk Administrator",
        is_admin=True,
        is_verified=True,
    )
    send_email(
        db,
        recipient_email=admin_email,
        subject=admin_tpl["subject"],
        html_body=admin_tpl["html"],
        text_body=admin_tpl["text"],
        event_type="ticket_assigned_admin",
        event_key=f"email:ticket_assigned:{event_suffix}:admin",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=None,
        recipient_verified=True,
    )


def send_ticket_priority_email(
    db: Session,
    ticket: Ticket,
    old_priority: str,
    new_priority: str,
    actor_name: str,
    event_suffix: str,
) -> None:
    requester = ticket.requester or db.query(User).filter(User.id == ticket.requester_id).first()
    if not requester:
        return
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    old_p_label = PRIORITY_LABELS.get(old_priority, old_priority)
    new_p_label = PRIORITY_LABELS.get(new_priority, new_priority)
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    updated_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
    assigned_grp = ticket.group.name if ticket.group else None

    from app.services.email_templates import render_ticket_field_update_email
    tpl = render_ticket_field_update_email(
        employee_name=requester.name,
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        field_name="Priority",
        old_value=old_p_label,
        new_value=new_p_label,
        assigned_group=assigned_grp,
        updated_by_name=actor_name,
        current_status=status_label,
        resolution_notes=None,
        updated_at=updated_str,
        ticket_url=_ticket_url(ticket),
    )
    send_email(
        db,
        recipient_email=requester.email,
        subject=tpl["subject"],
        html_body=tpl["html_body"],
        text_body=tpl["text_body"],
        event_type="ticket_priority_updated",
        event_key=f"email:ticket_priority:{event_suffix}:employee",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=requester.id,
        recipient_verified=bool(getattr(requester, "email_verified", False)),
    )




def send_ticket_status_email(
    db: Session,
    ticket: Ticket,
    old_status: str,
    new_status: str,
    event_suffix: str,
) -> None:
    if new_status not in MEANINGFUL_STATUS_EMAILS:
        return
    requester = ticket.requester or db.query(User).filter(User.id == ticket.requester_id).first()
    if not requester:
        return
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    priority_label = PRIORITY_LABELS.get(ticket.priority, ticket.priority)
    old_label = STATUS_LABELS.get(old_status, old_status.replace("_", " ").title())
    new_label = STATUS_LABELS.get(new_status, new_status.replace("_", " ").title())

    tpl = render_ticket_status_email(
        ticket_number=ticket_num,
        title=ticket.title,
        old_status_label=old_label,
        new_status_label=new_label,
        priority_label=priority_label,
        ticket_url=_ticket_url(ticket),
        recipient_name=requester.name,
        is_verified=bool(getattr(requester, "email_verified", False)),
    )
    send_email(
        db,
        recipient_email=requester.email,
        subject=tpl["subject"],
        html_body=tpl["html"],
        text_body=tpl["text"],
        event_type="ticket_status_updated",
        event_key=f"email:ticket_status:{event_suffix}:employee",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=requester.id,
        recipient_verified=bool(getattr(requester, "email_verified", False)),
    )


def send_ticket_resolution_email(
    db: Session,
    ticket: Ticket,
    resolution_notes: str,
    event_suffix: str,
) -> None:
    requester = ticket.requester or db.query(User).filter(User.id == ticket.requester_id).first()
    if not requester:
        return
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    resolved_str = (
        ticket.resolved_at.strftime("%Y-%m-%d %H:%M UTC")
        if ticket.resolved_at
        else _utc_now().strftime("%Y-%m-%d %H:%M UTC")
    )
    url = _ticket_url(ticket)

    emp_tpl = render_ticket_resolution_email(
        ticket_number=ticket_num,
        title=ticket.title,
        status_label=status_label,
        resolution_notes=resolution_notes,
        resolved_at_str=resolved_str,
        ticket_url=url,
        recipient_name=requester.name,
        is_admin=False,
        is_verified=bool(getattr(requester, "email_verified", False)),
    )
    send_email(
        db,
        recipient_email=requester.email,
        subject=emp_tpl["subject"],
        html_body=emp_tpl["html"],
        text_body=emp_tpl["text"],
        event_type="ticket_resolved",
        event_key=f"email:ticket_resolved:{event_suffix}:employee",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=requester.id,
        recipient_verified=bool(getattr(requester, "email_verified", False)),
    )

    admin_email = get_admin_notification_email()
    admin_tpl = render_ticket_resolution_email(
        ticket_number=ticket_num,
        title=ticket.title,
        status_label=status_label,
        resolution_notes=resolution_notes,
        resolved_at_str=resolved_str,
        ticket_url=url,
        recipient_name="NexDesk Administrator",
        is_admin=True,
        is_verified=True,
    )
    send_email(
        db,
        recipient_email=admin_email,
        subject=admin_tpl["subject"],
        html_body=admin_tpl["html"],
        text_body=admin_tpl["text"],
        event_type="ticket_resolved_admin",
        event_key=f"email:ticket_resolved:{event_suffix}:admin",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=None,
        recipient_verified=True,
    )


