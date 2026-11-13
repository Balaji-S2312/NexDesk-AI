"""Notification and email delivery log models for Module 9A."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.session import Base


class Notification(Base):
    """In-app notification record scoped to a specific recipient user."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id = Column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    ticket_number = Column(String(20), nullable=True, index=True)
    notification_type = Column(String(64), nullable=False, index=True)
    event_key = Column(String(160), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String(255), nullable=True)
    metadata_json = Column(Text, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    read_at = Column(DateTime(timezone=True), nullable=True)

    recipient = relationship("User", back_populates="notifications")
    ticket = relationship("Ticket")

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} user_id={self.recipient_user_id} "
            f"type='{self.notification_type}' is_read={self.is_read}>"
        )


class EmailDeliveryLog(Base):
    """Audit and reliability tracking record for outbound notification emails."""

    __tablename__ = "email_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    recipient_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_email = Column(String(255), nullable=False, index=True)
    recipient_verified = Column(Boolean, nullable=False, default=False)
    ticket_id = Column(
        Integer, ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ticket_number = Column(String(20), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    event_key = Column(String(160), unique=True, nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    delivery_status = Column(String(40), nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EmailDeliveryLog id={self.id} to='{self.recipient_email}' "
            f"event='{self.event_type}' status='{self.delivery_status}'>"
        )
