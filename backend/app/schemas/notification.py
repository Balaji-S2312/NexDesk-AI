"""Pydantic schemas for notifications and email delivery history (Module 9A)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_user_id: int
    ticket_id: Optional[int] = None
    ticket_number: Optional[str] = None
    notification_type: str
    title: str
    message: str
    link: Optional[str] = None
    metadata: Dict[str, Any] = {}
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListOut(BaseModel):
    items: List[NotificationOut]
    total: int
    unread_count: int


class UnreadCountOut(BaseModel):
    unread_count: int


class MarkAllReadOut(BaseModel):
    marked_count: int


class EmailDeliveryLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_user_id: Optional[int] = None
    recipient_email: str
    recipient_verified: bool
    ticket_id: Optional[int] = None
    ticket_number: Optional[str] = None
    event_type: str
    subject: str
    delivery_status: str
    attempt_count: int
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None


class NotificationConfigOut(BaseModel):
    admin_notification_email: str
    smtp_configured: bool
    smtp_host: str
    smtp_port: int
    smtp_from_email: str
    smtp_from_name: str
    smtp_use_tls: bool
    https_provider_configured: bool = False
    email_transport: str = "smtp"
