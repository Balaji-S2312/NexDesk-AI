from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="employee", index=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tickets_requested = relationship("Ticket", foreign_keys="[Ticket.requester_id]", back_populates="requester", cascade="all, delete-orphan")
    tickets_assigned = relationship("Ticket", foreign_keys="[Ticket.assignee_id]", back_populates="assignee")
    conversations = relationship("Conversation", back_populates="user")
    messages = relationship("Message", back_populates="sender")
    documents = relationship("Document", back_populates="creator")
    ticket_histories = relationship("TicketHistory", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    notifications = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' role='{self.role}'>"
