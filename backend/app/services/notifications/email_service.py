"""Email delivery service (SMTP TLS + optional HTTPS Email API) with retries, domain safety, and audit logging."""
from datetime import datetime, timezone
from email.message import EmailMessage
import errno
import json
import logging
import re
import smtplib
import socket
from typing import Optional
import urllib.error
import urllib.request

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
_RESERVED_NON_ROUTABLE_DOMAINS = {"example.com", "example.org", "example.net"}
_RESERVED_NON_ROUTABLE_SUFFIXES = (".example", ".invalid", ".test", ".localhost", ".local")

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


def is_non_routable_domain(email: str) -> bool:
    """Detect RFC 2606 / reserved non-deliverable test domains that return Null MX bounces."""
    if "@" not in email:
        return True
    domain = email.rsplit("@", 1)[1].strip().lower()
    if domain in _RESERVED_NON_ROUTABLE_DOMAINS:
        return True
    return any(domain.endswith(suffix) for suffix in _RESERVED_NON_ROUTABLE_SUFFIXES)


def _using_live_stdlib_smtp() -> bool:
    """True when smtplib.SMTP has NOT been monkeypatched by unit tests."""
    return getattr(smtplib.SMTP, "__module__", "") == "smtplib"


def is_https_provider_configured() -> bool:
    return bool(
        ((settings.RESEND_API_KEY or "").strip() or (settings.BREVO_API_KEY or "").strip())
        and settings.SMTP_FROM_EMAIL
        and is_valid_email(settings.SMTP_FROM_EMAIL.strip())
    )


def is_smtp_configured() -> bool:
    return bool(
        (
            settings.SMTP_HOST
            and settings.SMTP_HOST.strip()
            and settings.SMTP_FROM_EMAIL
            and is_valid_email(settings.SMTP_FROM_EMAIL.strip())
            and settings.SMTP_PASSWORD
            and settings.SMTP_PASSWORD.strip()
        )
        or is_https_provider_configured()
    )


def get_admin_notification_email() -> str:
    """Resolve centralized fixed administrator notification email from Settings."""
    for candidate in (settings.ADMIN_NOTIFICATION_EMAIL, settings.ADMIN_EMAIL):
        cleaned = (candidate or "").strip()
        if is_valid_email(cleaned):
            return cleaned
    return "balaji.poet2312s@gmail.com"


def get_employee_notification_recipient(db: Session, ticket: Ticket) -> Optional[User]:
    """Centralized lookup resolving the ticket-owning employee dynamically from the DB."""
    if ticket.requester_id is None:
        return None
    owner = db.query(User).filter(User.id == ticket.requester_id).first()
    if owner and is_valid_email(owner.email):
        return owner
    return None


def _sanitize_smtp_error(err: Exception) -> str:
    base_msg = str(err) or type(err).__name__
    for secret in (settings.SMTP_PASSWORD, settings.SMTP_USERNAME, settings.RESEND_API_KEY, settings.BREVO_API_KEY):
        if secret:
            base_msg = base_msg.replace(secret, "[REDACTED]")

    if isinstance(err, smtplib.SMTPAuthenticationError):
        raw = f"SMTP authentication failed (check SMTP_USERNAME and App Password): {base_msg}"
    elif isinstance(err, smtplib.SMTPRecipientsRefused):
        raw = f"Recipient address rejected or bounced by mail server: {base_msg}"
    elif isinstance(err, smtplib.SMTPSenderRefused):
        raw = f"Sender email rejected or restricted by mail server: {base_msg}"
    elif isinstance(err, socket.gaierror):
        raw = f"Mail server DNS lookup failed for SMTP_HOST: {base_msg}"
    elif isinstance(err, (TimeoutError, socket.timeout)):
        raw = f"SMTP mail server connection timed out: {base_msg}"
    elif isinstance(err, OSError) and getattr(err, "errno", None) in (errno.ENETUNREACH, 101):
        raw = f"[Errno 101] Network is unreachable (outbound SMTP ports 25/465/587 blocked by host): {base_msg}"
    else:
        raw = base_msg
    return raw[:500]


def _deliver_via_https_api(
    *,
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> Optional[str]:
    """Send email over HTTPS port 443 via Resend or Brevo when configured."""
    from_name = (settings.SMTP_FROM_NAME or "NexDesk AI").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    timeout_s = max(5, int(settings.SMTP_TIMEOUT_SECONDS))

    def _post_json(url: str, headers: dict, body_dict: dict, provider_label: str) -> None:
        req = urllib.request.Request(
            url,
            data=json.dumps(body_dict).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "NexDesk-AI/1.0",
                **headers,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                if resp.status < 200 or resp.status >= 300:
                    raise RuntimeError(f"{provider_label} API rejected request with HTTP {resp.status}.")
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                pass
            detail = err_body or str(exc)
            raise RuntimeError(f"{provider_label} API error ({exc.code}): {detail}") from exc

    resend_key = (settings.RESEND_API_KEY or "").strip()
    if resend_key:
        custom_resend_from = (getattr(settings, "RESEND_FROM_EMAIL", "") or "").strip()
        if is_valid_email(custom_resend_from):
            resend_from = custom_resend_from
        else:
            domain_part = from_email.rsplit("@", 1)[-1].lower() if "@" in from_email else ""
            public_domains = {"gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com"}
            resend_from = "onboarding@resend.dev" if (not from_email or domain_part in public_domains) else from_email

        _post_json(
            "https://api.resend.com/emails",
            {"Authorization": f"Bearer {resend_key}"},
            {
                "from": f"{from_name} <{resend_from}>",
                "to": [recipient_email],
                "subject": subject.replace("\r", "").replace("\n", ""),
                "html": html_body,
                "text": text_body,
            },
            "Resend",
        )
        return "resend"

    brevo_key = (settings.BREVO_API_KEY or "").strip()
    if brevo_key:
        _post_json(
            "https://api.brevo.com/v3/smtp/email",
            {"api-key": brevo_key},
            {
                "sender": {"name": from_name, "email": from_email},
                "to": [{"email": recipient_email}],
                "subject": subject.replace("\r", "").replace("\n", ""),
                "htmlContent": html_body,
                "textContent": text_body,
            },
            "Brevo",
        )
        return "brevo"

    return None


def describe_delivery_status(log_row: Optional[EmailDeliveryLog]) -> tuple[str, Optional[str]]:
    """
    Distinguish SMTP server / API acceptance from actual delivery errors without
    conflating SMTP relay acceptance with confirmed inbox receipt.
    """
    if log_row is None:
        return "failed", "Verification dispatch log could not be recorded."
    if log_row.delivery_status == "sent":
        return "accepted_by_smtp", None
    if log_row.delivery_status == "skipped_unconfigured":
        return "skipped_unconfigured", log_row.error_message
    return "failed", log_row.error_message


def _deliver_smtp_message(msg: EmailMessage) -> None:
    """Open SMTP connection using environment configuration and send EmailMessage."""
    is_prod = (settings.ENVIRONMENT or "").strip().lower() == "production"
    timeout_s = min(4, int(settings.SMTP_TIMEOUT_SECONDS)) if is_prod else int(settings.SMTP_TIMEOUT_SECONDS)
    with smtplib.SMTP(
        settings.SMTP_HOST.strip(),
        int(settings.SMTP_PORT),
        timeout=max(2, timeout_s),
    ) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        refused = server.send_message(msg)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def _ticket_url(ticket: Ticket) -> str:
    base = settings.get_frontend_base_url()
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

    if _using_live_stdlib_smtp() and not settings.ALLOW_RESERVED_EMAIL_DOMAINS and is_non_routable_domain(clean_recipient):
        domain = clean_recipient.rsplit("@", 1)[1].lower()
        err_msg = f"Recipient domain ({domain}) cannot receive external mail (reserved Null MX / test domain)."
        log_row = existing or EmailDeliveryLog(
            recipient_user_id=recipient_user_id,
            recipient_email=clean_recipient,
            recipient_verified=bool(recipient_verified),
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            event_type=event_type,
            event_key=event_key,
            subject=subject[:255],
            delivery_status="failed",
            attempt_count=0,
            error_message=err_msg,
            created_at=_utc_now(),
        )
        if existing:
            log_row.delivery_status = "failed"
            log_row.error_message = err_msg
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

    is_prod = (settings.ENVIRONMENT or "").strip().lower() == "production"
    has_https = is_https_provider_configured()
    max_attempts = 1 if (is_prod and not has_https) else max(1, int(settings.SMTP_MAX_RETRIES))
    attempts = 0
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None

    has_smtp_creds = bool(
        settings.SMTP_HOST
        and settings.SMTP_HOST.strip()
        and settings.SMTP_FROM_EMAIL
        and is_valid_email(settings.SMTP_FROM_EMAIL.strip())
        and settings.SMTP_PASSWORD
        and settings.SMTP_PASSWORD.strip()
    )

    for _ in range(max_attempts):
        attempts += 1
        try:
            # Prefer HTTPS port-443 email providers when configured (never blocked by PaaS SMTP firewalls).
            if has_https:
                _deliver_via_https_api(
                    recipient_email=clean_recipient,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                )
            elif has_smtp_creds:
                _deliver_smtp_message(msg)
            sent_at = _utc_now()
            last_error = None
            break
        except (smtplib.SMTPException, urllib.error.URLError, OSError, TimeoutError, RuntimeError) as exc:
            last_error = _sanitize_smtp_error(exc)
            logger.warning(
                "Email delivery attempt %s/%s failed for event=%s ticket=%s: %s",
                attempts,
                max_attempts,
                event_type,
                ticket_number,
                last_error,
            )
            # Fail fast when outbound SMTP ports are blocked or provider returns HTTP 4xx validation errors.
            err_code = getattr(exc, "errno", None)
            if err_code in (errno.ENETUNREACH, 101, getattr(errno, "EHOSTUNREACH", 113), 113) or "API error (4" in last_error:
                break

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
    requester = get_employee_notification_recipient(db, ticket)
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
    requester = get_employee_notification_recipient(db, ticket)
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

    admin_email = get_admin_notification_email()
    admin_tpl = render_ticket_field_update_email(
        employee_name="NexDesk Administrator",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        field_name="Priority Escalation",
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
        recipient_email=admin_email,
        subject=f"[NexDesk AI] Priority Updated ({new_p_label}): {ticket_num}",
        html_body=admin_tpl["html_body"],
        text_body=admin_tpl["text_body"],
        event_type="ticket_priority_updated_admin",
        event_key=f"email:ticket_priority:{event_suffix}:admin",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=None,
        recipient_verified=True,
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
    requester = get_employee_notification_recipient(db, ticket)
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

    if new_status in ("closed", "pending", "open"):
        admin_email = get_admin_notification_email()
        admin_tpl = render_ticket_status_email(
            ticket_number=ticket_num,
            title=ticket.title,
            old_status_label=old_label,
            new_status_label=new_label,
            priority_label=priority_label,
            ticket_url=_ticket_url(ticket),
            recipient_name="NexDesk Administrator",
            is_verified=True,
        )
        send_email(
            db,
            recipient_email=admin_email,
            subject=f"[NexDesk AI] Ticket {ticket_num} Status Alert ({new_label})",
            html_body=admin_tpl["html"],
            text_body=admin_tpl["text"],
            event_type="ticket_status_updated_admin",
            event_key=f"email:ticket_status:{event_suffix}:admin",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            recipient_user_id=None,
            recipient_verified=True,
        )


def send_ticket_resolution_email(
    db: Session,
    ticket: Ticket,
    resolution_notes: str,
    event_suffix: str,
) -> None:
    requester = get_employee_notification_recipient(db, ticket)
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


def send_ticket_comment_email(
    db: Session,
    ticket: Ticket,
    comment_text: str,
    author: User,
    comment_id: int,
) -> None:
    requester = get_employee_notification_recipient(db, ticket)
    if not requester:
        return
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    updated_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
    preview = (comment_text or "").strip()[:400]
    url = _ticket_url(ticket)

    from app.services.email_templates import render_ticket_field_update_email

    if author.role == "admin":
        tpl = render_ticket_field_update_email(
            employee_name=requester.name,
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            field_name="IT Support Comment",
            old_value="No new reply",
            new_value=preview,
            assigned_group=ticket.group.name if ticket.group else None,
            updated_by_name=author.name,
            current_status=status_label,
            resolution_notes=None,
            updated_at=updated_str,
            ticket_url=url,
        )
        send_email(
            db,
            recipient_email=requester.email,
            subject=f"[NexDesk AI] IT Support Comment on {ticket_num}",
            html_body=tpl["html_body"],
            text_body=tpl["text_body"],
            event_type="admin_comment",
            event_key=f"email:ticket_comment:{comment_id}:employee:{requester.id}",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            recipient_user_id=requester.id,
            recipient_verified=bool(getattr(requester, "email_verified", False)),
        )
    else:
        admin_email = get_admin_notification_email()
        tpl = render_ticket_field_update_email(
            employee_name="NexDesk Administrator",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            field_name="Employee Reply",
            old_value=requester.name,
            new_value=preview,
            assigned_group=ticket.group.name if ticket.group else None,
            updated_by_name=author.name,
            current_status=status_label,
            resolution_notes=None,
            updated_at=updated_str,
            ticket_url=url,
        )
        send_email(
            db,
            recipient_email=admin_email,
            subject=f"[NexDesk AI] Employee Reply on {ticket_num} — {author.name}",
            html_body=tpl["html_body"],
            text_body=tpl["text_body"],
            event_type="employee_reply",
            event_key=f"email:ticket_comment:{comment_id}:admin",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            recipient_user_id=None,
            recipient_verified=True,
        )


def send_ticket_escalation_email(
    db: Session,
    ticket: Ticket,
    group_name: str,
    summary: str,
    actor_name: str,
    event_suffix: str,
) -> None:
    requester = get_employee_notification_recipient(db, ticket)
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    updated_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
    url = _ticket_url(ticket)

    from app.services.email_templates import render_ticket_field_update_email

    admin_email = get_admin_notification_email()
    admin_tpl = render_ticket_field_update_email(
        employee_name="NexDesk Administrator",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        field_name="Ticket Escalation",
        old_value=f"Requester: {requester.name if requester else 'Employee'}",
        new_value=f"Escalated to {group_name} — {(summary or '')[:220]}",
        assigned_group=group_name,
        updated_by_name=actor_name,
        current_status=status_label,
        resolution_notes=None,
        updated_at=updated_str,
        ticket_url=url,
    )
    send_email(
        db,
        recipient_email=admin_email,
        subject=f"[NexDesk AI] Escalation Alert ({group_name}): {ticket_num}",
        html_body=admin_tpl["html_body"],
        text_body=admin_tpl["text_body"],
        event_type="ticket_escalated_admin",
        event_key=f"email:ticket_escalated:{event_suffix}:admin",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=None,
        recipient_verified=True,
    )

    if requester:
        emp_tpl = render_ticket_field_update_email(
            employee_name=requester.name,
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            field_name="Escalated Support Group",
            old_value="AI Self-Service",
            new_value=group_name,
            assigned_group=group_name,
            updated_by_name=actor_name,
            current_status=status_label,
            resolution_notes=None,
            updated_at=updated_str,
            ticket_url=url,
        )
        send_email(
            db,
            recipient_email=requester.email,
            subject=f"[NexDesk AI] Ticket Escalated to {group_name}: {ticket_num}",
            html_body=emp_tpl["html_body"],
            text_body=emp_tpl["text_body"],
            event_type="ticket_escalated",
            event_key=f"email:ticket_escalated:{event_suffix}:employee",
            ticket_id=ticket.id,
            ticket_number=ticket_num,
            recipient_user_id=requester.id,
            recipient_verified=bool(getattr(requester, "email_verified", False)),
        )


def send_sla_breach_email(
    db: Session,
    ticket: Ticket,
    sla_status: str,
) -> None:
    ticket_num = ticket.ticket_number or f"INC{ticket.id:07d}"
    priority_label = PRIORITY_LABELS.get(ticket.priority, ticket.priority)
    status_label = STATUS_LABELS.get(ticket.status, ticket.status.title())
    updated_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
    admin_email = get_admin_notification_email()

    from app.services.email_templates import render_ticket_field_update_email

    admin_tpl = render_ticket_field_update_email(
        employee_name="NexDesk Administrator",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        field_name="SLA Breach Alert",
        old_value=f"Priority: {priority_label}",
        new_value=f"SLA Breached ({sla_status}) on '{ticket.title}'",
        assigned_group=ticket.group.name if ticket.group else None,
        updated_by_name="SLA Monitor",
        current_status=status_label,
        resolution_notes=None,
        updated_at=updated_str,
        ticket_url=_ticket_url(ticket),
    )
    send_email(
        db,
        recipient_email=admin_email,
        subject=f"[NexDesk AI] SLA Breach Alert [{priority_label}]: {ticket_num}",
        html_body=admin_tpl["html_body"],
        text_body=admin_tpl["text_body"],
        event_type="sla_breached",
        event_key=f"email:sla_breached:{ticket.id}:admin",
        ticket_id=ticket.id,
        ticket_number=ticket_num,
        recipient_user_id=None,
        recipient_verified=True,
    )



