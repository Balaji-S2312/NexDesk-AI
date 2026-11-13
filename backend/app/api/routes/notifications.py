"""Notification & Email Delivery History API routes (Module 9A)."""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.database.session import get_db
from app.models.notification import EmailDeliveryLog
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.notification import (
    EmailDeliveryLogOut,
    MarkAllReadOut,
    NotificationConfigOut,
    NotificationListOut,
    NotificationOut,
    UnreadCountOut,
)
from app.services.notifications.email_service import (
    get_admin_notification_email,
    is_https_provider_configured,
    is_smtp_configured,
)
from app.services.notifications.notification_service import (
    NotificationAccessError,
    NotificationNotFoundError,
    get_unread_count,
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    serialize_notification,
    sync_sla_notifications,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    background_tasks: BackgroundTasks,
    unread_only: bool = Query(False),
    ticket_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return notifications belonging exclusively to the authenticated user."""
    if current_user.role == "admin" and ticket_id is None:
        try:
            sync_sla_notifications(db, background_tasks=background_tasks)
        except Exception:
            pass

    if ticket_id is not None and current_user.role != "admin":
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket or ticket.requester_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    return get_user_notifications(
        db,
        current_user,
        unread_only=unread_only,
        ticket_id=ticket_id,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def get_notifications_unread_count(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return unread notification count for the authenticated user."""
    if current_user.role == "admin":
        try:
            sync_sla_notifications(db, background_tasks=background_tasks)
        except Exception:
            pass
    return {"unread_count": get_unread_count(db, current_user)}


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def read_single_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark one notification as read after strict recipient ownership verification."""
    try:
        notif = mark_notification_read(db, notification_id, current_user)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NotificationAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return serialize_notification(notif)


@router.patch("/read-all", response_model=MarkAllReadOut)
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark every unread notification belonging to the current user as read."""
    count = mark_all_notifications_read(db, current_user)
    return {"marked_count": count}


@router.get("/email-history", response_model=List[EmailDeliveryLogOut])
def list_email_delivery_history(
    ticket_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List email delivery audit records.
    Employees see only emails addressed to their own user record; Admins see organization logs.
    """
    query = db.query(EmailDeliveryLog)
    if current_user.role != "admin":
        query = query.filter(EmailDeliveryLog.recipient_user_id == current_user.id)
        if ticket_id is not None:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket or ticket.requester_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    if ticket_id is not None:
        query = query.filter(EmailDeliveryLog.ticket_id == ticket_id)

    return (
        query.order_by(EmailDeliveryLog.created_at.desc(), EmailDeliveryLog.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/config", response_model=NotificationConfigOut)
def get_notification_config(
    _admin: User = Depends(require_admin),
):
    """Admin-only sanitized view of SMTP & notification routing settings (never returns SMTP_PASSWORD)."""
    has_https = is_https_provider_configured()
    smtp_ready = is_smtp_configured()
    transport = "https_api" if has_https else ("smtp" if smtp_ready else "none")
    return {
        "admin_notification_email": get_admin_notification_email(),
        "smtp_configured": smtp_ready,
        "smtp_host": settings.SMTP_HOST or "",
        "smtp_port": int(settings.SMTP_PORT),
        "smtp_from_email": settings.SMTP_FROM_EMAIL,
        "smtp_from_name": settings.SMTP_FROM_NAME,
        "smtp_use_tls": bool(settings.SMTP_USE_TLS),
        "https_provider_configured": has_https,
        "email_transport": transport,
    }
